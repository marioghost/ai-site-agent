"""Tests for source display status buckets."""
from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.database import SessionLocal, init_db
from app.models.chunk import Chunk
from app.repositories.source_repository import SourceRepository
from app.services.source_display_status import (
    DISPLAY_FAILED,
    DISPLAY_NEEDS_REFRESH,
    DISPLAY_PENDING,
    DISPLAY_READY,
    DISPLAY_SKIPPED,
    source_display_status,
)
from app.services.source_list_service import SourceListService
from app.utils.time_utils import utcnow


def _url(suffix: str) -> str:
    return f"https://src-{suffix}-{uuid.uuid4().hex[:8]}.example.com"


def test_pending_is_waiting():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        source, _ = repo.record_discovery(_url("p"), "page")
        assert source_display_status(source, chunk_count=0) == DISPLAY_PENDING
    finally:
        db.close()


def test_indexed_with_chunks_is_ready():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        source, _ = repo.record_discovery(_url("r"), "page")
        source.status = "indexed"
        source.indexed_at = utcnow()
        repo.save(source)
        db.add(
            Chunk(
                source_id=source.id,
                chunk_index=0,
                title="T",
                url=source.url,
                text="hello world",
                vector_id="v1",
            )
        )
        db.commit()
        assert source_display_status(source, chunk_count=1) == DISPLAY_READY
    finally:
        db.close()


def test_failed_and_skipped():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        fail, _ = repo.record_discovery(_url("f"), "page")
        fail.status = "error"
        repo.save(fail)
        skip, _ = repo.record_discovery(_url("s"), "page")
        skip.status = "skipped"
        repo.save(skip)
        assert source_display_status(fail) == DISPLAY_FAILED
        assert source_display_status(skip) == DISPLAY_SKIPPED
    finally:
        db.close()


def test_error_with_chunks_shows_needs_refresh():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        source, _ = repo.record_discovery(_url("e"), "page")
        source.status = "error"
        source.error_message = "Fetch failed: timeout"
        repo.save(source)
        db.add(
            Chunk(
                source_id=source.id,
                chunk_index=0,
                title="T",
                url=source.url,
                text="hello world",
                vector_id="v1",
            )
        )
        db.commit()
        assert source_display_status(source, chunk_count=1) == DISPLAY_NEEDS_REFRESH
    finally:
        db.close()


def test_list_bucket_filter():
    init_db()
    db = SessionLocal()
    try:
        svc = SourceListService(db)
        url = _url("lr")
        repo = SourceRepository(db)
        source, _ = repo.record_discovery(url, "page")
        source.status = "indexed"
        source.indexed_at = utcnow()
        source.next_refresh_at = utcnow() + timedelta(hours=168)
        repo.save(source)
        db.add(
            Chunk(
                source_id=source.id,
                chunk_index=0,
                title="T",
                url=source.url,
                text="content",
                vector_id="v2",
            )
        )
        db.commit()
        ready_items, _ = svc.list_sources(
            page=1, page_size=500, bucket="ready", url_contains=url
        )
        assert len(ready_items) == 1
        assert ready_items[0]["id"] == source.id
        assert ready_items[0]["display_status"] == DISPLAY_READY
    finally:
        db.close()
