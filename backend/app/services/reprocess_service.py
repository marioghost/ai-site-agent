"""Reprocess already-indexed sources with updated extraction/classification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_config
from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.boilerplate_detector_service import BoilerplateDetectorService
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.content_extraction_constants import EXTRACTION_VERSION
from app.services.indexing_service import IndexingService
from app.services.knowledge_version_service import KnowledgeVersionService

logger = get_logger(__name__)


@dataclass
class ReprocessOptions:
    scope: str = "all"
    source_ids: list[int] = field(default_factory=list)
    status: list[str] = field(default_factory=lambda: ["indexed"])
    rebuild_chunks: bool = True
    rebuild_embeddings: bool = True
    reclassify_document_types: bool = True
    recalculate_content_hints: bool = True
    remove_boilerplate: bool = True
    invalidate_caches: bool = True
    limit: int | None = None
    dry_run: bool = False
    document_type_filter: str | None = None
    needs_reprocess_only: bool = False
    high_boilerplate_only: bool = False


@dataclass
class ReprocessPreview:
    selected_sources: int = 0
    estimated_chunks: int = 0
    sample_boilerplate_ratios: list[float] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


class ReprocessService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = SourceRepository(db)

    def _select_stmt(self, options: ReprocessOptions):
        stmt = select(Source)
        if options.scope == "selected" and options.source_ids:
            stmt = stmt.where(Source.id.in_(options.source_ids))
        elif options.scope == "ready":
            stmt = stmt.where(Source.status.in_(("indexed", "ready")))
        elif options.scope == "by_status" and options.status:
            stmt = stmt.where(Source.status.in_(tuple(options.status)))
        else:
            stmt = stmt.where(Source.status == "indexed")

        if options.needs_reprocess_only:
            stmt = stmt.where(Source.needs_reprocess.is_(True))
        if options.document_type_filter:
            stmt = stmt.where(Source.document_type == options.document_type_filter)
        if options.high_boilerplate_only:
            stmt = stmt.where(Source.boilerplate_ratio >= 0.55)
        outdated = or_(
            Source.extraction_version != EXTRACTION_VERSION,
            Source.extraction_version.is_(None),
            Source.extraction_version == "",
        )
        if options.scope == "by_filter":
            stmt = stmt.where(outdated)
        return stmt.order_by(Source.id.asc())

    def select_sources(self, options: ReprocessOptions) -> list[Source]:
        stmt = self._select_stmt(options)
        if options.limit:
            stmt = stmt.limit(options.limit)
        return list(self.db.scalars(stmt).all())

    def iter_source_batches(
        self, options: ReprocessOptions, *, batch_size: int | None = None
    ):
        """Keyset pagination: ``WHERE id > last_id ORDER BY id LIMIT batch``."""
        size = batch_size or get_config().db_write_batch_size
        last_id = 0
        yielded = 0
        limit = options.limit
        while True:
            stmt = self._select_stmt(options).where(Source.id > last_id).limit(size)
            batch = list(self.db.scalars(stmt).all())
            if not batch:
                break
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    break
                if len(batch) > remaining:
                    batch = batch[:remaining]
            yield batch
            yielded += len(batch)
            last_id = batch[-1].id
            if limit is not None and yielded >= limit:
                break
            if len(batch) < size:
                break

    def count_sources(self, options: ReprocessOptions) -> int:
        from sqlalchemy import func as sqla_func

        stmt = select(sqla_func.count()).select_from(
            self._select_stmt(options).subquery()
        )
        return int(self.db.execute(stmt).scalar_one())

    def preview(self, options: ReprocessOptions) -> ReprocessPreview:
        sources = self.select_sources(options)
        chunk_count = self.repo.count_chunks_for_sources([s.id for s in sources])
        ratios = sorted(
            [float(s.boilerplate_ratio or 0.0) for s in sources if s.boilerplate_ratio],
            reverse=True,
        )[:8]
        return ReprocessPreview(
            selected_sources=len(sources),
            estimated_chunks=chunk_count,
            sample_boilerplate_ratios=ratios,
            source_urls=[s.url for s in sources[:20]],
        )

    def run(
        self,
        options: ReprocessOptions,
        *,
        on_progress: Callable[[str, str, dict], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict:
        if options.dry_run:
            preview = self.preview(options)
            return {
                "dry_run": True,
                "selected_sources": preview.selected_sources,
                "estimated_chunks": preview.estimated_chunks,
                "sample_boilerplate_ratios": preview.sample_boilerplate_ratios,
                "source_urls": preview.source_urls,
            }

        def tick(phase: str, message: str, extra: dict | None = None) -> None:
            if on_progress:
                on_progress(phase, message, extra or {})

        selected_total = self.count_sources(options)
        tick(
            "selecting_sources",
            f"Selected {selected_total} sources",
            {"selected": selected_total, "processed": 0, "failed": 0, "skipped": 0},
        )

        detector = BoilerplateDetectorService(self.db)
        if options.remove_boilerplate:
            tick(
                "detecting_boilerplate",
                "Building boilerplate phrase index",
                {
                    "selected": selected_total,
                    "processed": 0,
                    "failed": 0,
                    "skipped": 0,
                },
            )
            detector.build_from_sources()

        indexer = IndexingService(self.db, self.settings)
        if options.remove_boilerplate:
            indexer.set_boilerplate_detector(detector)

        processed = 0
        failed = 0
        skipped = 0
        chunks_rebuilt = 0
        stopped = False

        def progress_extra(url: str | None = None) -> dict:
            payload: dict = {
                "selected": selected_total,
                "processed": processed,
                "failed": failed,
                "skipped": skipped,
            }
            if url:
                payload["url"] = url
            return payload

        for batch in self.iter_source_batches(options):
            for source in batch:
                if cancel_check and cancel_check():
                    stopped = True
                    tick(
                        "stopped",
                        "Reprocess stopped by user",
                        progress_extra(source.url),
                    )
                    break

                tick(
                    "loading_source",
                    f"Loading source: {source.url}",
                    progress_extra(source.url),
                )
                try:

                    def source_tick(stage: str, msg: str) -> None:
                        tick(
                            "rebuilding_chunks",
                            msg,
                            progress_extra(source.url),
                        )

                    tick(
                        "rebuilding_chunks",
                        f"Reprocessing {source.url}",
                        progress_extra(source.url),
                    )
                    outcome = indexer.index_source(
                        source,
                        force=True,
                        on_progress=source_tick,
                    )
                    if outcome.status == "indexed":
                        processed += 1
                        if outcome.detail and "chunks" in outcome.detail:
                            try:
                                chunks_rebuilt += int(outcome.detail.split()[0])
                            except ValueError:
                                chunks_rebuilt += 1
                        source.needs_reprocess = False
                        self.repo.save(source)
                    elif outcome.status == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                        if source.status == "error":
                            source.status = "indexed"
                            source.needs_reprocess = True
                            self.repo.save(source)
                        tick(
                            "failed",
                            f"Failed: {source.url} — {outcome.detail or outcome.status}",
                            progress_extra(source.url),
                        )
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    logger.warning("Reprocess failed for %s: %s", source.url, exc)
                    tick(
                        "failed",
                        f"Failed: {source.url} — {exc}",
                        progress_extra(source.url),
                    )
            self.db.commit()
            if stopped:
                break

        if stopped:
            return {
                "stopped": True,
                "selected_sources": selected_total,
                "processed_sources": processed,
                "failed_sources": failed,
                "skipped_sources": skipped,
                "chunks_rebuilt": chunks_rebuilt,
            }

        if options.invalidate_caches and not stopped:
            tick("invalidating_cache", "Invalidating retrieval and answer caches")
            KnowledgeVersionService(self.db).bump()
            CacheInvalidationService(self.db, self.settings).invalidate_all_caches(
                "reprocess_existing"
            )

        tick(
            "completed",
            f"Reprocess complete: {processed} updated, {failed} failed, {skipped} skipped",
            {
                "selected": selected_total,
                "processed": processed,
                "failed": failed,
                "skipped": skipped,
            },
        )
        return {
            "selected_sources": selected_total,
            "processed_sources": processed,
            "failed_sources": failed,
            "skipped_sources": skipped,
            "chunks_rebuilt": chunks_rebuilt,
        }


def mark_sources_needs_reprocess(db: Session, *, reason: str = "pipeline_update") -> int:
    """Mark indexed sources as needing reprocess after profile/pipeline changes."""
    rows = list(
        db.scalars(select(Source).where(Source.status == "indexed")).all()
    )
    count = 0
    for row in rows:
        if not row.needs_reprocess or row.extraction_version != EXTRACTION_VERSION:
            row.needs_reprocess = True
            count += 1
    if count:
        db.commit()
        logger.info("Marked %d sources needs_reprocess (%s)", count, reason)
    return count
