"""Generate Source Intelligence profiles for indexed sources (optimized)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.settings import Settings
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.knowledge_profile_service import KnowledgeProfileService
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.settings_flags import setting_bool
from app.services.source_intelligence_llm_cache_service import (
    SourceIntelligenceLLMCacheService,
)
from app.services.source_intelligence_perf import (
    IntelligenceRunStats,
    llm_enabled_for_settings,
    should_skip_source,
)
from app.services.source_intelligence_service import (
    SourceIntelligenceService,
    SourceProfile,
)
from app.utils.time_utils import utcnow

logger = get_logger(__name__)


@dataclass
class IntelligenceOptions:
    scope: str = "needs_intelligence"
    source_ids: list[int] = field(default_factory=list)
    limit: int | None = None
    dry_run: bool = False
    generate_summaries: bool = False

    @property
    def force_reprocess(self) -> bool:
        return self.scope == "all"


@dataclass
class IntelligencePreview:
    selected_sources: int = 0
    sample_profiles: list[dict] = field(default_factory=list)
    would_skip_unchanged: int = 0
    would_call_llm: int = 0
    llm_cache_hits_possible: int = 0
    estimated_time_rules_only: float = 0.0
    estimated_time_with_llm: float = 0.0
    estimated_db_batches: int = 0


@dataclass
class _ProcessOutcome:
    source_id: int
    action: str
    profile: SourceProfile | None = None
    error: str | None = None
    rules_ms: float = 0.0
    llm_ms: float = 0.0
    merge_ms: float = 0.0
    llm_cache_hits: int = 0
    llm_calls: int = 0
    llm_failures: int = 0


class SourceIntelligenceGenerationService:
    RULES_MS_ESTIMATE = 35.0
    LLM_MS_ESTIMATE = 25000.0

    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = SourceRepository(db)
        self.profile = KnowledgeProfileService.from_settings(settings)

    def _base_stmt(self, options: IntelligenceOptions):
        stmt = select(Source).where(Source.status == "indexed")
        if options.scope == "selected" and options.source_ids:
            stmt = stmt.where(Source.id.in_(options.source_ids))
        elif options.scope == "needs_intelligence":
            stmt = stmt.where(Source.needs_intelligence.is_(True))
        return stmt

    def count_sources(self, options: IntelligenceOptions) -> int:
        stmt = select(func.count()).select_from(Source).where(Source.status == "indexed")
        if options.scope == "selected" and options.source_ids:
            stmt = stmt.where(Source.id.in_(options.source_ids))
        elif options.scope == "needs_intelligence":
            stmt = stmt.where(Source.needs_intelligence.is_(True))
        return int(self.db.scalar(stmt) or 0)

    def iter_source_id_pages(
        self, options: IntelligenceOptions, *, page_size: int
    ) -> Iterator[list[int]]:
        last_id = 0
        remaining = options.limit
        while True:
            limit = page_size
            if remaining is not None:
                if remaining <= 0:
                    break
                limit = min(limit, remaining)
            stmt = (
                select(Source.id)
                .where(Source.status == "indexed")
                .where(Source.id > last_id)
            )
            if options.scope == "selected" and options.source_ids:
                stmt = stmt.where(Source.id.in_(options.source_ids))
            elif options.scope == "needs_intelligence":
                stmt = stmt.where(Source.needs_intelligence.is_(True))
            stmt = stmt.order_by(Source.id.asc()).limit(limit)
            ids = list(self.db.scalars(stmt).all())
            if not ids:
                break
            last_id = ids[-1]
            if remaining is not None:
                remaining -= len(ids)
            yield ids

    def select_sources(self, options: IntelligenceOptions) -> list[Source]:
        """Legacy helper — prefer paginated iteration for large corpora."""
        stmt = self._base_stmt(options).order_by(Source.id.asc())
        if options.limit:
            stmt = stmt.limit(options.limit)
        return list(self.db.scalars(stmt).all())

    def _perf_settings(self) -> dict:
        return {
            "db_batch_size": int(getattr(self.settings, "source_intelligence_db_batch_size", 50) or 50),
            "page_size": int(getattr(self.settings, "source_intelligence_page_size", 100) or 100),
            "worker_count": int(getattr(self.settings, "source_intelligence_worker_count", 0) or 0),
            "progress_flush_every": int(
                getattr(self.settings, "source_intelligence_progress_flush_every_sources", 10) or 10
            ),
            "progress_flush_interval": float(
                getattr(self.settings, "source_intelligence_progress_flush_interval_seconds", 3) or 3
            ),
            "invalidation_mode": getattr(
                self.settings, "source_intelligence_cache_invalidation_mode", "version_bump_only"
            )
            or "version_bump_only",
        }

    def _resolve_worker_count(self) -> int:
        perf = self._perf_settings()
        configured = perf["worker_count"]
        if configured <= 0:
            configured = 2  # auto default (PostgreSQL handles concurrent writes)
        return max(1, configured)

    def estimate(self, options: IntelligenceOptions) -> IntelligencePreview:
        perf = self._perf_settings()
        page_size = perf["page_size"]
        llm_on = llm_enabled_for_settings(self.settings)
        selected = 0
        would_skip = 0
        would_call_llm = 0
        cache_hits = 0
        cache_svc = SourceIntelligenceLLMCacheService(self.db)
        for ids in self.iter_source_id_pages(options, page_size=page_size):
            rows = self.db.scalars(select(Source).where(Source.id.in_(ids))).all()
            for source in rows:
                selected += 1
                if should_skip_source(
                    source,
                    self.settings,
                    force_reprocess=options.force_reprocess,
                    llm_enabled=llm_on,
                ):
                    would_skip += 1
                    continue
                if llm_on and (options.generate_summaries or setting_bool(
                    self.settings, "enable_llm_source_intelligence", default=True
                )):
                    would_call_llm += 1
                    content_hash = source.content_hash or ""
                    if content_hash:
                        key = cache_svc.build_key(
                            content_hash=content_hash,
                            llm_model=self.settings.llm_model or "",
                            settings=self.settings,
                            language=source.source_language or "unknown",
                        )
                        if cache_svc.get_profile(key) is not None:
                            cache_hits += 1
        db_batches = max(
            1,
            (selected - would_skip + perf["db_batch_size"] - 1) // perf["db_batch_size"],
        )
        rules_only_ms = (selected - would_skip) * self.RULES_MS_ESTIMATE
        llm_ms = (would_call_llm - cache_hits) * self.LLM_MS_ESTIMATE + cache_hits * 5
        return IntelligencePreview(
            selected_sources=selected,
            would_skip_unchanged=would_skip,
            would_call_llm=would_call_llm,
            llm_cache_hits_possible=cache_hits,
            estimated_time_rules_only=round(rules_only_ms / 1000.0, 1),
            estimated_time_with_llm=round((rules_only_ms + llm_ms) / 1000.0, 1),
            estimated_db_batches=db_batches,
        )

    def preview(
        self,
        options: IntelligenceOptions,
        *,
        on_progress: Callable[[str, str, dict], None] | None = None,
    ) -> IntelligencePreview:
        sources = self.select_sources(options)
        samples = []
        sample_total = min(12, len(sources))
        for index, src in enumerate(sources[:12]):
            if on_progress:
                on_progress(
                    "previewing",
                    src.url,
                    {
                        "url": src.url,
                        "source_id": src.id,
                        "selected": len(sources),
                        "processed": index,
                    },
                )
            sp = SourceIntelligenceService.build_profile(
                src,
                self.profile,
                settings=self.settings,
                use_llm=options.generate_summaries or None,
                db=self.db,
            )
            samples.append(sp.to_dict())
        estimate = self.estimate(options)
        estimate.sample_profiles = samples
        return estimate

    def build_profile_for_source(
        self,
        source: Source,
        options: IntelligenceOptions,
        *,
        db: Session | None = None,
        stats: IntelligenceRunStats | None = None,
    ) -> SourceProfile:
        t0 = time.monotonic()
        profile = SourceIntelligenceService.build_profile(
            source,
            self.profile,
            settings=self.settings,
            use_llm=options.generate_summaries or None,
            db=db or self.db,
            stats=stats,
        )
        if stats is not None:
            stats.record_ms("rules_ms", (time.monotonic() - t0) * 1000)
        return profile

    def apply_profile(
        self,
        source: Source,
        profile: SourceProfile,
        *,
        now,
        commit: bool = True,
    ) -> None:
        SourceIntelligenceService.apply_to_source(
            source, profile, settings=self.settings, now=now
        )
        self.repo.flush(source)
        if commit:
            self.repo.commit()

    def finalize_generation(
        self,
        *,
        on_progress: Callable[[str, str, dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        mode = (
            getattr(self.settings, "source_intelligence_cache_invalidation_mode", None)
            or "version_bump_only"
        )
        if on_progress:
            on_progress(
                "invalidating_cache",
                "Bumping knowledge version / clearing caches",
                {"current_phase": "finalize"},
            )
        KnowledgeVersionService(self.db).bump()
        if mode == "delete_all":
            CacheInvalidationService(self.db, self.settings).invalidate_all_caches(
                "source_intelligence_generated"
            )
        elif mode == "delete_related":
            CacheInvalidationService(self.db, self.settings).invalidate_retrieval_cache(
                "source_intelligence_generated"
            )
        if should_stop and should_stop():
            from app.services.knowledge_understanding.rebuild import (
                UnderstandingRebuildStopped,
            )

            raise UnderstandingRebuildStopped()
        # Knowledge Understanding Layer — rebuild site-wide model after SI batch.
        # This embeds all SI concepts and can take minutes; progress must stay alive.
        from app.services.knowledge_understanding.rebuild import (
            UnderstandingRebuildService,
        )

        UnderstandingRebuildService(self.db, self.settings).rebuild_after_si(
            on_progress=on_progress,
            should_stop=should_stop,
        )

    @staticmethod
    def _process_source_in_worker(
        source_id: int,
        options: IntelligenceOptions,
        settings_id: int,
    ) -> _ProcessOutcome:
        db = SessionLocal()
        try:
            settings = db.get(Settings, settings_id)
            source = db.get(Source, source_id)
            if settings is None or source is None:
                return _ProcessOutcome(source_id=source_id, action="error", error="missing")
            llm_on = llm_enabled_for_settings(settings)
            if should_skip_source(
                source,
                settings,
                force_reprocess=options.force_reprocess,
                llm_enabled=llm_on,
            ):
                return _ProcessOutcome(source_id=source_id, action="skip")
            svc = SourceIntelligenceGenerationService(db, settings)
            local_stats = IntelligenceRunStats()
            t0 = time.monotonic()
            profile = svc.build_profile_for_source(source, options, db=db, stats=local_stats)
            rules_ms = (time.monotonic() - t0) * 1000
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            return _ProcessOutcome(
                source_id=source_id,
                action="update",
                profile=profile,
                rules_ms=rules_ms,
                llm_cache_hits=local_stats.llm_cache_hits,
                llm_calls=local_stats.llm_calls,
                llm_failures=local_stats.llm_failures,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Source intelligence worker failed for %s: %s", source_id, exc)
            return _ProcessOutcome(source_id=source_id, action="error", error=str(exc))
        finally:
            db.close()

    def run(
        self,
        options: IntelligenceOptions,
        *,
        on_progress: Callable[[str, str, dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        stats: IntelligenceRunStats | None = None,
    ) -> dict:
        perf = self._perf_settings()
        page_size = perf["page_size"]
        batch_size = perf["db_batch_size"]
        worker_count = self._resolve_worker_count()
        run_stats = stats or IntelligenceRunStats(
            worker_count=worker_count,
            batch_size=batch_size,
            page_size=page_size,
            force_reprocess=options.force_reprocess,
        )

        def tick(phase: str, message: str, extra: dict | None = None) -> None:
            if on_progress:
                payload = run_stats.to_dict()
                if extra:
                    payload.update(extra)
                on_progress(phase, message, payload)

        if options.dry_run:
            preview = self.estimate(options)
            return {
                "dry_run": True,
                "selected_sources": preview.selected_sources,
                "would_skip_unchanged": preview.would_skip_unchanged,
                "would_call_llm": preview.would_call_llm,
                "llm_cache_hits_possible": preview.llm_cache_hits_possible,
                "estimated_time_rules_only": preview.estimated_time_rules_only,
                "estimated_time_with_llm": preview.estimated_time_with_llm,
                "estimated_db_batches": preview.estimated_db_batches,
            }

        run_stats.selected_sources = self.count_sources(options)
        tick(
            "analyzing_sources",
            f"Analyzing {run_stats.selected_sources} sources",
            {"selected": run_stats.selected_sources, "processed": 0, "current_phase": "select_sources"},
        )

        now = utcnow()
        pending_in_batch = 0
        settings_id = self.settings.id

        def flush_batch() -> None:
            nonlocal pending_in_batch
            if pending_in_batch <= 0:
                return
            t0 = time.monotonic()
            try:
                self.repo.commit()
                run_stats.db_batches += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Batch commit failed: %s", exc)
                self.repo.rollback()
            finally:
                run_stats.record_ms("db_flush_ms", (time.monotonic() - t0) * 1000)
                pending_in_batch = 0

        def apply_update(source: Source, profile: SourceProfile) -> None:
            nonlocal pending_in_batch
            t0 = time.monotonic()
            SourceIntelligenceService.apply_to_source(
                source, profile, settings=self.settings, now=now
            )
            from app.services.epistemic_memory.memory_integration_service import (
                EpistemicMemoryIntegrationService,
            )

            EpistemicMemoryIntegrationService(self.db, self.settings).shadow_write_after_si(
                source, profile
            )
            run_stats.record_ms("apply_profile_ms", (time.monotonic() - t0) * 1000)
            self.repo.flush(source)
            pending_in_batch += 1
            run_stats.updated_sources += 1
            if pending_in_batch >= batch_size:
                flush_batch()

        def report_progress(source: Source | None, source_id: int) -> None:
            tick(
                "updating_profiles",
                source.url if source else str(source_id),
                {
                    "source_id": source_id,
                    "url": source.url if source else "",
                    "processed": run_stats.processed_sources,
                    "updated": run_stats.updated_sources,
                    "skipped_unchanged": run_stats.skipped_unchanged,
                    "llm_cache_hits": run_stats.llm_cache_hits,
                    "llm_calls": run_stats.llm_calls,
                    "current_phase": "updating_profiles",
                },
            )

        use_pool = worker_count > 1
        for id_page in self.iter_source_id_pages(options, page_size=page_size):
            if should_stop and should_stop():
                break
            if not use_pool:
                for source_id in id_page:
                    if should_stop and should_stop():
                        break
                    source = self.repo.get(source_id)
                    if source is None:
                        continue
                    llm_on = llm_enabled_for_settings(self.settings)
                    if should_skip_source(
                        source,
                        self.settings,
                        force_reprocess=options.force_reprocess,
                        llm_enabled=llm_on,
                    ):
                        run_stats.processed_sources += 1
                        run_stats.skipped_unchanged += 1
                        report_progress(source, source_id)
                        continue
                    profile = self.build_profile_for_source(
                        source, options, db=self.db, stats=run_stats
                    )
                    apply_update(source, profile)
                    run_stats.processed_sources += 1
                    report_progress(source, source_id)
            else:
                pool = ThreadPoolExecutor(max_workers=worker_count)
                stop_requested = False
                try:
                    futures = {
                        pool.submit(
                            self._process_source_in_worker,
                            source_id,
                            options,
                            settings_id,
                        ): source_id
                        for source_id in id_page
                    }
                    for future in as_completed(futures):
                        if should_stop and should_stop():
                            stop_requested = True
                            for pending in futures:
                                pending.cancel()
                            break
                        source_id = futures[future]
                        try:
                            outcome = future.result()
                        except Exception as exc:  # noqa: BLE001
                            logger.exception(
                                "Source intelligence future failed for %s: %s",
                                source_id,
                                exc,
                            )
                            continue
                        source = self.repo.get(source_id)
                        run_stats.processed_sources += 1
                        run_stats.llm_cache_hits += outcome.llm_cache_hits
                        run_stats.llm_calls += outcome.llm_calls
                        run_stats.llm_failures += outcome.llm_failures
                        if outcome.action == "skip":
                            run_stats.skipped_unchanged += 1
                            report_progress(source, source_id)
                            continue
                        if outcome.action != "update" or outcome.profile is None or source is None:
                            report_progress(source, source_id)
                            continue
                        apply_update(source, outcome.profile)
                        report_progress(source, source_id)
                finally:
                    # Default `with ThreadPoolExecutor` waits for ALL submitted futures on
                    # exit — that made Stop appear broken during multi-worker SI runs.
                    pool.shutdown(wait=not stop_requested, cancel_futures=True)
                if stop_requested:
                    break

        flush_batch()
        if should_stop and should_stop():
            result = run_stats.to_dict()
            result["stopped"] = True
            return result

        t0 = time.monotonic()
        tick(
            "invalidating_cache",
            "Finalizing — rebuilding knowledge understanding",
            {"current_phase": "finalize"},
        )
        from app.services.knowledge_understanding.rebuild import (
            UnderstandingRebuildStopped,
        )

        try:
            self.finalize_generation(on_progress=tick, should_stop=should_stop)
        except UnderstandingRebuildStopped:
            result = run_stats.to_dict()
            result["stopped"] = True
            result["stopped_during"] = "understanding_rebuild"
            return result
        run_stats.record_ms("finalize_ms", (time.monotonic() - t0) * 1000)
        tick(
            "completed",
            f"Updated {run_stats.updated_sources} source profiles",
            {"updated": run_stats.updated_sources},
        )
        return run_stats.to_dict()
