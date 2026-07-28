"""Filtered source listing for the Sources dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.indexing_planner_service import IndexingPlannerService
from app.services.source_display_status import (
    DISPLAY_FAILED,
    DISPLAY_NEEDS_REFRESH,
    DISPLAY_PENDING,
    DISPLAY_READY,
    DISPLAY_SKIPPED,
    source_display_status,
)
from app.utils.time_utils import utcnow

PAGE_TYPES = frozenset({"page", "html"})
FILE_TYPES = frozenset({"pdf", "docx", "txt"})


class SourceListService:
    def __init__(self, db: Session) -> None:
        self.db = db
        settings = SettingsRepository(db).get_or_create()
        self._planner = IndexingPlannerService(
            page_refresh_hours=settings.indexed_page_refresh_interval_hours,
            file_refresh_hours=settings.indexed_file_refresh_interval_hours,
        )

    def list_sources(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        status: str | None = None,
        bucket: str | None = None,
        source_type: str | None = None,
        url_contains: str | None = None,
        date_range: str | None = None,
        exclude_fixtures: bool = True,
    ) -> tuple[list[dict], int]:
        chunk_counts = dict(
            self.db.execute(
                select(Chunk.source_id, func.count()).group_by(Chunk.source_id)
            ).all()
        )

        stmt = select(Source)
        if exclude_fixtures:
            stmt = stmt.where(
                ~Source.url.ilike("%fixture.example%"),
                ~Source.url.ilike("fixture.%"),
            )
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(Source.title.ilike(like), Source.url.ilike(like))
            )
        if status:
            stmt = stmt.where(Source.status == status.lower())
        if source_type == "page":
            stmt = stmt.where(Source.source_type.in_(sorted(PAGE_TYPES)))
        elif source_type == "file":
            stmt = stmt.where(Source.source_type.in_(sorted(FILE_TYPES)))
        elif source_type:
            stmt = stmt.where(Source.source_type == source_type)
        if url_contains:
            stmt = stmt.where(Source.url.ilike(f"%{url_contains.strip()}%"))

        now = utcnow()
        if date_range == "today":
            cutoff = now - timedelta(days=1)
            stmt = stmt.where(Source.indexed_at >= cutoff)
        elif date_range == "week":
            cutoff = now - timedelta(days=7)
            stmt = stmt.where(Source.indexed_at >= cutoff)
        elif date_range == "month":
            cutoff = now - timedelta(days=30)
            stmt = stmt.where(Source.indexed_at >= cutoff)

        sources = list(self.db.scalars(stmt.order_by(Source.updated_at.desc())).all())

        if bucket:
            sources = [
                s
                for s in sources
                if source_display_status(
                    s,
                    chunk_count=int(chunk_counts.get(s.id, 0)),
                    planner=self._planner,
                    now=now,
                )
                == bucket
            ]

        total = len(sources)
        start = (page - 1) * page_size
        page_items = sources[start : start + page_size]

        items = [
            self._serialize(s, chunk_counts.get(s.id, 0), now=now) for s in page_items
        ]
        return items, total

    def get_detail(self, source_id: int) -> dict | None:
        source = self.db.get(Source, source_id)
        if source is None:
            return None
        chunks = list(
            self.db.scalars(
                select(Chunk)
                .where(Chunk.source_id == source_id)
                .order_by(Chunk.chunk_index)
            ).all()
        )
        chunk_count = len(chunks)
        now = utcnow()
        preview = " ".join(c.text for c in chunks[:3])[:1200]
        word_count = sum(len((c.text or "").split()) for c in chunks)
        char_count = sum(len(c.text or "") for c in chunks) or source.content_length or 0
        hint = chunks[0].content_type_hint if chunks else "generic"
        base = self._serialize(source, chunk_count, now=now)
        intelligence: dict = {}
        try:
            intelligence = json.loads(source.intelligence_json or "{}")
        except json.JSONDecodeError:
            intelligence = {}
        base.update(
            {
                "preview_text": preview,
                "word_count": word_count,
                "char_count": char_count,
                "content_type_hint": hint,
                "last_checked_at": source.last_checked_at,
                "semantic_profile": intelligence if isinstance(intelligence, dict) else {},
                "profile_version": source.profile_version or "",
                "llm_summary": source.llm_summary or "",
            }
        )
        return base

    def _serialize(self, source: Source, chunk_count: int, *, now: datetime) -> dict:
        display = source_display_status(
            source, chunk_count=chunk_count, planner=self._planner, now=now
        )
        return {
            "id": source.id,
            "source_type": source.source_type,
            "url": source.url,
            "title": source.title,
            "document_type": source.document_type,
            "content_hash": source.content_hash,
            "content_length": source.content_length or 0,
            "status": source.status,
            "display_status": display,
            "chunk_count": chunk_count,
            "error_message": source.error_message,
            "indexed_at": source.indexed_at,
            "last_checked_at": source.last_checked_at,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
        }
