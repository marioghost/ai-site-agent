"""Tests for GET /api/index/status and queue-preview schema."""
from __future__ import annotations

import json

from app.models.index_job import IndexJob
from app.repositories.index_job_repository import IndexJobRepository
from app.services.indexing_progress import IndexingProgress
from app.utils.time_utils import utcnow


def test_index_status_schema(client, auth_headers):
    res = client.get("/api/index/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("idle", "running", "completed", "failed", "stopped")
    assert "discovery" in data
    assert "queue" in data
    assert "pages" in data
    assert "files" in data
    assert "stage" in data
    assert "progress" in data
    assert "summary" in data
    assert "recent_activity" in data
    assert "advanced" in data
    assert "alive_state" in data
    for section in ("discovery", "queue", "pages", "files"):
        for value in data[section].values():
            assert isinstance(value, int)
    assert isinstance(data["progress"]["is_indeterminate"], bool)
    assert isinstance(data["recent_activity"], list)


def test_index_status_user_friendly_fields(client, auth_headers):
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        job = IndexJobRepository(db).create()
        progress = IndexingProgress()
        progress.set_stage(
            "extracting_text",
            phase="processing_pages",
            action="Extracting readable text",
            message="Text extracted: 4250 chars",
        )
        progress.set_current_url(
            "https://example.com/about",
            url_type="page",
            message="Processing page: https://example.com/about",
        )
        progress.queue.queued_pages_for_this_run = 200
        progress.pages.processed_pages = 100
        progress.apply_to_job(job)
        job.status = "running"
        job.started_at = utcnow()
        job.updated_at = utcnow()
        job.log_json = json.dumps(
            [
                {
                    "timestamp": "2026-06-26T10:00:00Z",
                    "level": "info",
                    "message": "Processing page: https://example.com/about",
                }
            ]
        )
        IndexJobRepository(db).save(job)
    finally:
        db.close()

    res = client.get("/api/index/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "extracting_text"
    assert data["current_url"] == "https://example.com/about"
    assert data["current_url_type"] == "page"
    assert data["last_activity_message"] is not None
    assert data["heartbeat_counter"] >= 1
    assert data["progress"]["percent"] == 50.0
    assert data["progress"]["is_indeterminate"] is False
    assert len(data["recent_activity"]) >= 1


def test_index_status_nested_counters_from_progress_json(client, auth_headers):
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        job = IndexJobRepository(db).create()
        progress = IndexingProgress()
        progress.current_phase = "processing_pages"
        progress.discovery.discovered_urls = 700
        progress.discovery.discovered_pages = 700
        progress.discovery.newly_discovered_urls = 340
        progress.discovery.already_known_urls = 360
        progress.queue.new_pages_waiting = 340
        progress.queue.fresh_pages_skipped_until_refresh = 360
        progress.queue.queued_pages_for_this_run = 200
        progress.pages.processed_pages = 25
        progress.pages.indexed_new_pages = 25
        progress.apply_to_job(job)
        job.status = "running"
        job.started_at = utcnow()
        job.updated_at = utcnow()
        job.log_json = json.dumps(
            [{"timestamp": "t", "level": "info", "message": "test"}]
        )
        IndexJobRepository(db).save(job)
    finally:
        db.close()

    res = client.get("/api/index/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "running"
    assert data["current_phase"] == "processing_pages"
    assert data["discovery"]["discovered_urls"] == 700
    assert data["discovery"]["newly_discovered_urls"] == 340
    assert data["queue"]["queued_pages_for_this_run"] == 200
    assert data["queue"]["fresh_pages_skipped_until_refresh"] == 360
    assert data["pages"]["processed_pages"] == 25
    assert data["pages"]["indexed_new_pages"] == 25
    assert isinstance(data["log_tail"], list)
    assert data["processed_pages"] == 25


def test_queue_preview_schema(client, auth_headers):
    res = client.get("/api/index/queue-preview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "queue" in data
    q = data["queue"]
    for key in (
        "new_pages_waiting",
        "failed_pages_waiting",
        "stale_pages_waiting",
        "fresh_pages_skipped_until_refresh",
        "total_pages_waiting",
        "queued_pages_for_this_run",
    ):
        assert key in q
        assert isinstance(q[key], int)
    assert "max_pages_per_run" in data
    assert "estimated_runs_remaining" in data
