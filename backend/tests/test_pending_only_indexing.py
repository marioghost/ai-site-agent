"""Tests for pending-only indexing mode."""
from __future__ import annotations

import uuid

from app.core.database import SessionLocal, init_db
from app.models.chunk import Chunk
from app.repositories.source_repository import SourceRepository
from app.utils.time_utils import utcnow


def _url(suffix: str) -> str:
    return f"https://pending-{suffix}-{uuid.uuid4().hex[:8]}.example.com"


def test_list_waiting_page_sources_excludes_ready():
    init_db()
    db = SessionLocal()
    try:
        repo = SourceRepository(db)
        pending, _ = repo.record_discovery(_url("w"), "page")
        ready, _ = repo.record_discovery(_url("r"), "page")
        ready.status = "indexed"
        ready.indexed_at = utcnow()
        repo.save(ready)
        db.add(
            Chunk(
                source_id=ready.id,
                chunk_index=0,
                title="T",
                url=ready.url,
                text="body",
                vector_id="v1",
            )
        )
        db.commit()

        waiting = repo.list_waiting_page_sources()
        ids = {s.id for s in waiting}
        assert pending.id in ids
        assert ready.id not in ids
    finally:
        db.close()
