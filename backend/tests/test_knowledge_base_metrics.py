"""Tests for knowledge base readiness metrics."""
from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.database import SessionLocal, init_db
from app.models.chunk import Chunk
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.knowledge_base_metrics_service import KnowledgeBaseMetricsService
from app.utils.time_utils import utcnow


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _seed_source(
    db,
    *,
    url: str,
    status: str = "pending",
    source_type: str = "page",
    with_chunks: bool = False,
    stale: bool = False,
) -> Source:
    repo = SourceRepository(db)
    source, _ = repo.record_discovery(url, source_type)
    source.status = status
    now = utcnow()
    if status == "indexed":
        source.indexed_at = now
        source.content_hash = "abc123"
        source.content_length = 100
        if stale:
            source.next_refresh_at = now - timedelta(hours=1)
        else:
            source.next_refresh_at = now + timedelta(hours=168)
    repo.save(source)
    if with_chunks:
        db.add(
            Chunk(
                source_id=source.id,
                chunk_index=0,
                title="Test",
                url=source.url,
                text="Sample indexed content for testing.",
                vector_id=f"vec-{source.id}",
            )
        )
        db.commit()
    return source


def test_pending_sources_counted_as_waiting():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        _seed_source(db, url=f"https://kb-{_suffix()}.example.com/p1")
        _seed_source(db, url=f"https://kb-{_suffix()}.example.com/p2")
        after = svc.compute()
        assert after.waiting == before.waiting + 2
        assert after.ready_to_use == before.ready_to_use
    finally:
        db.close()


def test_indexed_with_chunks_counted_as_ready():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        _seed_source(
            db,
            url=f"https://kb-{_suffix()}.example.com/ready",
            status="indexed",
            with_chunks=True,
        )
        after = svc.compute()
        assert after.ready_to_use == before.ready_to_use + 1
        assert after.chunks_count == before.chunks_count + 1
        assert after.vectors_count == before.vectors_count + 1
    finally:
        db.close()


def test_failed_and_skipped_buckets():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        _seed_source(db, url=f"https://kb-{_suffix()}.example.com/fail", status="error")
        _seed_source(db, url=f"https://kb-{_suffix()}.example.com/skip", status="skipped")
        after = svc.compute()
        assert after.failed == before.failed + 1
        assert after.skipped == before.skipped + 1
    finally:
        db.close()


def test_stale_indexed_counted_as_needs_refresh_and_ready():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        _seed_source(
            db,
            url=f"https://kb-{_suffix()}.example.com/stale",
            status="indexed",
            with_chunks=True,
            stale=True,
        )
        after = svc.compute()
        assert after.ready_to_use == before.ready_to_use + 1
        assert after.needs_refresh == before.needs_refresh + 1
    finally:
        db.close()


def test_readiness_percent_calculation():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        for i in range(3):
            _seed_source(
                db,
                url=f"https://kb-{_suffix()}.example.com/r{i}",
                status="indexed",
                with_chunks=True,
            )
        for i in range(7):
            _seed_source(db, url=f"https://kb-{_suffix()}.example.com/w{i}")
        _seed_source(db, url=f"https://kb-{_suffix()}.example.com/skip", status="skipped")
        after = svc.compute()
        added_ready = 3
        added_waiting = 7
        added_skipped = 1
        assert after.ready_to_use == before.ready_to_use + added_ready
        assert after.waiting == before.waiting + added_waiting
        assert after.skipped == before.skipped + added_skipped
        new_relevant = (
            (after.ready_to_use - before.ready_to_use)
            + (after.waiting - before.waiting)
            + (after.failed - before.failed)
        )
        expected_pct = round(
            (before.ready_to_use + added_ready)
            / (before.ready_to_use + before.waiting + before.failed + new_relevant)
            * 100,
            1,
        )
        assert after.readiness_percent == expected_pct
    finally:
        db.close()


def test_indexed_without_chunks_counts_as_waiting():
    init_db()
    db = SessionLocal()
    try:
        svc = KnowledgeBaseMetricsService(db)
        before = svc.compute()
        _seed_source(
            db,
            url=f"https://kb-{_suffix()}.example.com/no-chunks",
            status="indexed",
            with_chunks=False,
        )
        after = svc.compute()
        assert after.ready_to_use == before.ready_to_use
        assert after.waiting == before.waiting + 1
    finally:
        db.close()


def test_overview_api_schema(client, auth_headers):
    res = client.get("/api/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "knowledge_base" in data
    kb = data["knowledge_base"]
    for key in (
        "total_sources",
        "ready_to_use",
        "waiting",
        "needs_refresh",
        "failed",
        "skipped",
        "readiness_percent",
        "chunks_count",
    ):
        assert key in kb
    assert kb["total_sources"] >= kb["ready_to_use"]
