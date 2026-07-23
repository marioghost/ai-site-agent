"""Reprocess job progress is exposed through the unified status API."""
from __future__ import annotations

import json

from app.repositories.index_job_repository import IndexJobRepository
from app.services.indexing_progress import IndexingProgress
from app.utils.time_utils import utcnow


def test_reprocess_progress_maps_to_status(client, auth_headers):
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        job = IndexJobRepository(db).create()
        progress = IndexingProgress()
        progress.apply_reprocess_tick(
            phase="rebuilding_chunks",
            message="Reprocessing https://example.com/about",
            url="https://example.com/about",
            selected=120,
            processed=15,
            failed=2,
            skipped=1,
        )
        progress.apply_to_job(job)
        payload = json.loads(job.progress_json or "{}")
        payload["job_kind"] = "reprocess"
        job.progress_json = json.dumps(payload, ensure_ascii=False)
        job.status = "running"
        job.started_at = utcnow()
        job.updated_at = utcnow()
        job.log_json = json.dumps(
            [
                {
                    "timestamp": "2026-06-26T10:00:00Z",
                    "level": "info",
                    "message": "Reprocessing https://example.com/about",
                }
            ]
        )
        IndexJobRepository(db).save(job)
    finally:
        db.close()

    res = client.get("/api/index/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["run_mode"] == "reprocess"
    assert data["current_url"] == "https://example.com/about"
    assert data["progress"]["selected_total"] == 120
    assert data["progress"]["processed_total"] == 18
    assert data["progress"]["is_indeterminate"] is False
    assert data["progress"]["percent"] == 15.0
    assert data["summary"]["errors"] == 2
    assert data["summary"]["updated"] == 15
