"""Knowledge base readiness metrics for the Overview dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.source import Source
from app.repositories.settings_repository import SettingsRepository
from app.services.indexing_planner_service import CandidateClass, IndexingPlannerService
from app.utils.time_utils import utcnow

PAGE_TYPES = frozenset({"page", "html"})


@dataclass(frozen=True)
class KnowledgeBaseMetrics:
    total_sources: int
    ready_to_use: int
    waiting: int
    needs_refresh: int
    failed: int
    skipped: int
    readiness_percent: float
    ready_pages: int
    ready_files: int
    waiting_pages: int
    waiting_files: int
    chunks_count: int
    vectors_count: int
    last_indexed_at: datetime | None

    def as_dict(self) -> dict:
        return {
            "total_sources": self.total_sources,
            "ready_to_use": self.ready_to_use,
            "waiting": self.waiting,
            "needs_refresh": self.needs_refresh,
            "failed": self.failed,
            "skipped": self.skipped,
            "readiness_percent": self.readiness_percent,
            "ready_pages": self.ready_pages,
            "ready_files": self.ready_files,
            "waiting_pages": self.waiting_pages,
            "waiting_files": self.waiting_files,
            "chunks_count": self.chunks_count,
            "vectors_count": self.vectors_count,
            "last_indexed_at": self.last_indexed_at,
        }


class KnowledgeBaseMetricsService:
    """Compute how much of the knowledge base is ready for RAG answers."""

    def __init__(self, db: Session) -> None:
        self.db = db
        settings = SettingsRepository(db).get_or_create()
        self._planner = IndexingPlannerService(
            page_refresh_hours=settings.indexed_page_refresh_interval_hours,
            file_refresh_hours=settings.indexed_file_refresh_interval_hours,
        )

    def compute(self, *, now: datetime | None = None) -> KnowledgeBaseMetrics:
        from app.services.metrics_cache import knowledge_metrics_cache

        cached = knowledge_metrics_cache.get()
        if cached is not None:
            return KnowledgeBaseMetrics(**cached)

        now = now or utcnow()
        sources = list(self.db.scalars(select(Source)).all())

        chunk_counts: dict[int, int] = dict(
            self.db.execute(
                select(Chunk.source_id, func.count())
                .group_by(Chunk.source_id)
            ).all()
        )

        ready = waiting = needs_refresh = failed = skipped = 0
        ready_pages = ready_files = waiting_pages = waiting_files = 0

        last_indexed_at: datetime | None = None

        for source in sources:
            status = (source.status or "pending").lower()
            is_page = (source.source_type or "page").lower() in PAGE_TYPES
            chunks = int(chunk_counts.get(source.id, 0))
            has_chunks = chunks > 0

            if source.indexed_at is not None:
                if last_indexed_at is None or source.indexed_at > last_indexed_at:
                    last_indexed_at = source.indexed_at

            if status == "error":
                failed += 1
                continue

            if status == "skipped":
                skipped += 1
                continue

            if status == "indexed" and has_chunks:
                ready += 1
                if is_page:
                    ready_pages += 1
                else:
                    ready_files += 1
                if self._planner.classify(source, now=now) is CandidateClass.STALE:
                    needs_refresh += 1
                continue

            waiting += 1
            if is_page:
                waiting_pages += 1
            else:
                waiting_files += 1

        total_relevant = ready + waiting + failed
        readiness_percent = (
            round(ready / total_relevant * 100, 1) if total_relevant > 0 else 0.0
        )

        chunks_count = int(
            self.db.execute(select(func.count()).select_from(Chunk)).scalar_one()
        )
        vectors_count = int(
            self.db.execute(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.vector_id.isnot(None))
            ).scalar_one()
        )

        metrics = KnowledgeBaseMetrics(
            total_sources=len(sources),
            ready_to_use=ready,
            waiting=waiting,
            needs_refresh=needs_refresh,
            failed=failed,
            skipped=skipped,
            readiness_percent=readiness_percent,
            ready_pages=ready_pages,
            ready_files=ready_files,
            waiting_pages=waiting_pages,
            waiting_files=waiting_files,
            chunks_count=chunks_count,
            vectors_count=vectors_count,
            last_indexed_at=last_indexed_at,
        )
        knowledge_metrics_cache.set(metrics.as_dict())
        return metrics
