"""Repository for Source and Chunk persistence."""
from __future__ import annotations

from datetime import datetime
from math import ceil

from sqlalchemy import Text, delete, func, or_, select, update
from sqlalchemy.orm import Session, load_only
from sqlalchemy import inspect as sa_inspect

from app.models.chunk import Chunk
from app.models.source import Source
from app.services.indexing_planner_service import IndexingPlannerService
from app.utils.time_utils import to_naive_utc, utcnow

# Columns needed by IndexingPlannerService.classify / queue planning.
# Omitting Text blobs (extracted_text, intelligence_json, …) keeps long runs
# from retaining multi-GB of page bodies in the SQLAlchemy identity map.
_PLANNER_SOURCE_COLUMNS = (
    Source.id,
    Source.url,
    Source.source_type,
    Source.status,
    Source.next_refresh_at,
    Source.indexed_at,
    Source.first_seen_at,
    Source.last_seen_at,
    Source.last_checked_at,
    Source.index_attempts,
    Source.content_hash,
    Source.title,
)


def _source_text_attr_names() -> tuple[str, ...]:
    """ORM Text columns on Source — derived from the model, not a manual map."""
    return tuple(
        col.key
        for col in sa_inspect(Source).columns
        if isinstance(col.type, Text)
    )


class SourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, source_id: int) -> Source | None:
        return self.db.get(Source, source_id)

    def get_by_url(self, url: str) -> Source | None:
        return self.db.execute(
            select(Source).where(Source.url == url)
        ).scalar_one_or_none()

    def list(
        self, page: int = 1, page_size: int = 50, status: str | None = None
    ) -> tuple[list[Source], int]:
        stmt = select(Source)
        count_stmt = select(func.count()).select_from(Source)
        if status:
            stmt = stmt.where(Source.status == status)
            count_stmt = count_stmt.where(Source.status == status)
        total = self.db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(Source.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_by_urls(self, urls: list[str], *, lean: bool = False) -> list[Source]:
        if not urls:
            return []
        stmt = select(Source).where(Source.url.in_(urls))
        if lean:
            stmt = stmt.options(load_only(*_PLANNER_SOURCE_COLUMNS))
        return list(self.db.scalars(stmt).all())

    def list_by_source_types(self, source_types: set[str], *, lean: bool = False) -> list[Source]:
        if not source_types:
            return []
        stmt = select(Source).where(Source.source_type.in_(sorted(source_types)))
        if lean:
            stmt = stmt.options(load_only(*_PLANNER_SOURCE_COLUMNS))
        return list(self.db.scalars(stmt).all())

    def record_discovery(
        self,
        url: str,
        source_type: str,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> tuple[Source, bool]:
        """Register a discovered URL without processing it. Returns (source, created)."""
        now = now or utcnow()
        source = self.get_by_url(url)
        created = source is None
        if source is None:
            source = Source(
                url=url,
                source_type=source_type,
                status="pending",
                first_seen_at=now,
                last_seen_at=now,
                next_refresh_at=now,
            )
            self.db.add(source)
        else:
            source.last_seen_at = now
            if source.first_seen_at is None:
                source.first_seen_at = now
            if source.next_refresh_at is None and source.status != "indexed":
                source.next_refresh_at = now
            self.db.add(source)
        if commit:
            self.db.commit()
            self.db.refresh(source)
        else:
            self.db.flush()
        return source, created

    def upsert(self, url: str, source_type: str) -> Source:
        """Backward-compatible upsert used by reindex endpoints."""
        source, _created = self.record_discovery(url, source_type)
        return source

    def list_page_sources(self, *, lean: bool = True) -> list[Source]:
        page_types = {"page", "html"}
        stmt = select(Source).where(Source.source_type.in_(sorted(page_types)))
        if lean:
            stmt = stmt.options(load_only(*_PLANNER_SOURCE_COLUMNS))
        return list(self.db.scalars(stmt).all())

    def list_waiting_page_sources(self, *, lean: bool = True) -> list[Source]:
        """Pages not yet ready for RAG (pending / not indexed / indexed without chunks)."""
        page_types = {"page", "html"}
        has_chunks = select(Chunk.source_id).distinct()
        stmt = (
            select(Source)
            .where(Source.source_type.in_(sorted(page_types)))
            .where(~Source.status.in_(("error", "skipped")))
            .where(
                or_(
                    Source.status != "indexed",
                    ~Source.id.in_(has_chunks),
                )
            )
        )
        if lean:
            stmt = stmt.options(load_only(*_PLANNER_SOURCE_COLUMNS))
        return list(self.db.scalars(stmt).all())

    def release_source(self, source: Source) -> None:
        """Drop Text payloads and remove the row from the session identity map."""
        for attr in _source_text_attr_names():
            if attr in source.__dict__:
                setattr(source, attr, None)
        try:
            self.db.expunge(source)
        except Exception:  # noqa: BLE001
            try:
                self.db.expire(source)
            except Exception:  # noqa: BLE001
                pass

    def _count_pages_by_class(
        self,
        *,
        source_types: set[str],
        now: datetime,
    ) -> dict[str, int]:
        """SQL aggregate counts matching IndexingPlannerService.classify()."""
        now_naive = to_naive_utc(now) or utcnow()
        type_filter = Source.source_type.in_(sorted(source_types))

        def _scalar(*where) -> int:
            return int(
                self.db.scalar(select(func.count()).select_from(Source).where(type_filter, *where))
                or 0
            )

        new_pages = _scalar(Source.status.in_(("pending", "new")))
        failed_pages = _scalar(Source.status == "error")
        skipped_pages = _scalar(Source.status == "skipped")
        fresh_pages = _scalar(
            Source.status == "indexed",
            Source.next_refresh_at.isnot(None),
            Source.next_refresh_at > now_naive,
        )
        stale_pages = _scalar(
            Source.status == "indexed",
            or_(Source.next_refresh_at.is_(None), Source.next_refresh_at <= now_naive),
        )
        return {
            "new": new_pages,
            "failed": failed_pages,
            "skipped": skipped_pages,
            "fresh": fresh_pages,
            "stale": stale_pages,
        }

    def queue_preview(
        self,
        *,
        page_refresh_hours: int,
        file_refresh_hours: int,
        max_pages_per_run: int = 0,
        source_types: set[str] | None = None,
    ) -> dict[str, int]:
        types = source_types or {"page", "html"}
        now = utcnow()
        counts = self._count_pages_by_class(source_types=types, now=now)
        new_pages_waiting = counts["new"]
        failed_pages_waiting = counts["failed"]
        skipped_pages_waiting = counts["skipped"]
        stale_pages_waiting = counts["stale"]
        fresh_pages_skipped_until_refresh = counts["fresh"]
        total_pages_waiting = (
            new_pages_waiting
            + failed_pages_waiting
            + skipped_pages_waiting
            + stale_pages_waiting
        )
        if max_pages_per_run > 0:
            queued_pages_for_this_run = min(total_pages_waiting, max_pages_per_run)
            estimated_runs_remaining = (
                ceil(total_pages_waiting / max_pages_per_run) if total_pages_waiting else 0
            )
        else:
            queued_pages_for_this_run = total_pages_waiting
            estimated_runs_remaining = 1 if total_pages_waiting else 0

        return {
            "new_pages_waiting": new_pages_waiting,
            "failed_pages_waiting": failed_pages_waiting,
            "stale_pages_waiting": stale_pages_waiting,
            "fresh_pages_skipped_until_refresh": fresh_pages_skipped_until_refresh,
            "skipped_pages_waiting": skipped_pages_waiting,
            "total_pages_waiting": total_pages_waiting,
            "queued_pages_for_this_run": queued_pages_for_this_run,
            "max_pages_per_run": max_pages_per_run,
            "estimated_runs_remaining": estimated_runs_remaining,
            "new_pages": new_pages_waiting,
            "failed_pages": failed_pages_waiting,
            "stale_pages": stale_pages_waiting,
            "fresh_pages": fresh_pages_skipped_until_refresh,
            "queued_pages": queued_pages_for_this_run,
            "total_sources": total_pages_waiting + fresh_pages_skipped_until_refresh,
        }

    def queue_preview_legacy(
        self,
        *,
        page_refresh_hours: int,
        file_refresh_hours: int,
        max_pages_per_run: int = 0,
        source_types: set[str] | None = None,
    ) -> dict[str, int]:
        """Full in-memory planner pass (used only when exact ordering is required)."""
        stmt = select(Source)
        if source_types:
            stmt = stmt.where(Source.source_type.in_(sorted(source_types)))
        sources = list(self.db.scalars(stmt).all())
        page_planner = IndexingPlannerService(
            page_refresh_hours=page_refresh_hours,
            file_refresh_hours=file_refresh_hours,
        )
        preview = page_planner.build_queue_preview(
            sources, max_pages_per_run=max_pages_per_run
        )
        return preview.as_dict()

    def save(self, source: Source) -> Source:
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def flush(self, source: Source | None = None) -> None:
        if source is not None:
            self.db.add(source)
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def delete(self, source: Source) -> None:
        self.db.delete(source)
        self.db.commit()

    def delete_all(self) -> int:
        """Delete every source and its chunks. Returns number of sources removed."""
        total = self.count()
        self.db.execute(delete(Chunk))
        self.db.execute(delete(Source))
        self.db.commit()
        return total

    def count(self) -> int:
        return self.db.execute(select(func.count()).select_from(Source)).scalar_one()

    def count_chunks(self) -> int:
        return self.db.execute(select(func.count()).select_from(Chunk)).scalar_one()

    def delete_chunks_for_source(self, source_id: int) -> None:
        self.db.execute(delete(Chunk).where(Chunk.source_id == source_id))
        self.db.commit()

    def add_chunks(self, chunks: list[Chunk]) -> None:
        self.db.add_all(chunks)
        self.db.commit()

    def get_chunks_for_source(self, source_id: int) -> list[Chunk]:
        return list(
            self.db.execute(
                select(Chunk).where(Chunk.source_id == source_id)
            ).scalars().all()
        )

    def count_chunks_for_source(self, source_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.source_id == source_id)
            )
            or 0
        )

    def count_chunks_for_sources(self, source_ids: list[int]) -> int:
        if not source_ids:
            return 0
        return int(
            self.db.scalar(
                select(func.count()).select_from(Chunk).where(Chunk.source_id.in_(source_ids))
            )
            or 0
        )

    def count_needs_reprocess(self) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Source)
                .where(Source.needs_reprocess.is_(True))
            )
            or 0
        )

    def repair_error_sources_with_chunks(self) -> int:
        """Sources marked error while chunks remain — restore indexed + retry flag."""
        chunk_source_ids = select(Chunk.source_id).distinct()
        result = self.db.execute(
            update(Source)
            .where(Source.status == "error")
            .where(Source.id.in_(chunk_source_ids))
            .values(status="indexed", needs_reprocess=True)
        )
        self.db.commit()
        return result.rowcount or 0
