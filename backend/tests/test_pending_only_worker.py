"""Regression: pending_only worker must not crash on startup."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.core.database import SessionLocal, init_db
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.source_repository import SourceRepository
from app.services.indexing_service import IndexOutcome, IndexingService
from app.services.indexing_worker_service import IndexingWorker, _Overrides


def _url() -> str:
    return f"https://worker-pending-{uuid.uuid4().hex[:8]}.example.com"


def test_pending_only_worker_completes_without_crash():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        repo.record_discovery(_url(), "page")
    finally:
        db.close()

    worker = IndexingWorker()

    def fake_index(self, source, **kwargs):
        return IndexOutcome(status="indexed", detail="mocked")

    with patch.object(IndexingService, "index_source", fake_index):
        job_id = worker.start(_Overrides(pending_only=True))
        assert worker._thread is not None
        worker._thread.join(timeout=10)

    db = SessionLocal()
    try:
        job = IndexJobRepository(db).get(job_id)
        assert job is not None
        assert job.status == "completed", job.log_json
    finally:
        db.close()
