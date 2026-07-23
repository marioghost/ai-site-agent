"""Indexing API: start/stop a full-site index job and report status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_operator
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.source import Source
from app.repositories.index_job_repository import IndexJobRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.common import MessageResponse
from app.schemas.indexing import (
    GenerateSourceIntelligenceRequest,
    GenerateSourceIntelligenceResponse,
    IndexJobStatus,
    IndexQueuePreview,
    IndexStartRequest,
    ReprocessExistingRequest,
    ReprocessExistingResponse,
)
from app.services.source_intelligence_generation_service import (
    IntelligenceOptions,
    SourceIntelligenceGenerationService,
)
from app.services.reprocess_service import ReprocessOptions
from app.services.reprocess_worker_service import reprocess_worker
from app.services.source_intelligence_worker_service import source_intelligence_worker
from app.services.queue_preview_cache import queue_preview_cache
from app.utils.time_utils import utcnow
from app.services.indexing_status_service import job_to_status, preview_to_response
from app.services.indexing_worker_service import _Overrides, indexing_worker
from app.services.knowledge_version_service import KnowledgeVersionService
from app.services.lexical_index_service import LexicalIndexService
from app.services.qdrant_service import QdrantService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/index", tags=["indexing"])

# Throttle stale-job healing: avoid writing on every 2s status poll.
_stale_job_healed_at: float | None = None


def _overrides_from(payload: IndexStartRequest) -> _Overrides:
    return _Overrides(
        site_url=payload.site_url,
        sitemap_url=payload.sitemap_url,
        crawl_depth=payload.crawl_depth,
        allowed_domains=payload.allowed_domains,
        deny_url_patterns=payload.deny_url_patterns,
        max_pages_per_run=payload.max_pages_per_run,
        max_files_per_run=payload.max_files_per_run,
        scan_mode=payload.scan_mode,
        enable_file_indexing=payload.enable_file_indexing,
        scan_all_pages=payload.scan_all_pages,
        scan_all_files=payload.scan_all_files,
        force_reindex=payload.force_reindex or False,
        pending_only=payload.pending_only or False,
    )


@router.post("/start", response_model=MessageResponse)
def start_indexing(
    payload: IndexStartRequest,
    _user=Depends(require_operator),
) -> MessageResponse:
    if source_intelligence_worker.is_running():
        raise HTTPException(
            status_code=409, detail="A Source Intelligence job is already running"
        )
    if reprocess_worker.is_running():
        raise HTTPException(status_code=409, detail="A reprocess job is already running")
    queue_preview_cache.invalidate()
    try:
        job_id = indexing_worker.start(_overrides_from(payload))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=f"Indexing started (job {job_id})")


@router.post("/stop", response_model=MessageResponse)
def stop_indexing(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    if source_intelligence_worker.is_running():
        source_intelligence_worker.stop()
        return MessageResponse(message="Source Intelligence stop requested")
    if reprocess_worker.is_running():
        reprocess_worker.stop()
        return MessageResponse(message="Reprocess stop requested")
    if indexing_worker.is_running():
        indexing_worker.stop()
        return MessageResponse(message="Stop requested")

    job = IndexJobRepository(db).latest()
    if job is not None and job.status == "running":
        job.status = "stopped"
        job.finished_at = utcnow()
        job.current_phase = "stopped"
        IndexJobRepository(db).save(job)
        queue_preview_cache.invalidate()
        return MessageResponse(message="Stale running job marked as stopped")

    raise HTTPException(status_code=409, detail="No indexing job is running")


@router.post("/reindex-all", response_model=MessageResponse)
def reindex_all(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> MessageResponse:
    if indexing_worker.is_running():
        raise HTTPException(
            status_code=409, detail="An indexing job is already running"
        )

    settings = SettingsRepository(db).get_or_create()

    try:
        QdrantService(collection=settings.qdrant_collection).delete_collection()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed clearing Qdrant collection: %s", exc)

    removed = SourceRepository(db).delete_all()
    logger.info("reindex-all cleared %d sources", removed)
    queue_preview_cache.invalidate()

    try:
        from app.services.cache_invalidation_service import CacheInvalidationService

        LexicalIndexService(db).delete_all()
        KnowledgeVersionService(db).bump()
        CacheInvalidationService(db, settings).invalidate_all_caches("reindex_all")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed clearing caches on reindex-all: %s", exc)

    job_id = indexing_worker.start(_Overrides(force_reindex=True))
    return MessageResponse(
        message=f"Cleared {removed} sources; reindexing started (job {job_id})"
    )


@router.post("/reprocess-existing", response_model=ReprocessExistingResponse)
def reprocess_existing(
    payload: ReprocessExistingRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> ReprocessExistingResponse:
    if source_intelligence_worker.is_running():
        raise HTTPException(
            status_code=409, detail="A Source Intelligence job is already running"
        )
    if reprocess_worker.is_running():
        raise HTTPException(
            status_code=409, detail="A reprocess job is already running"
        )
    if indexing_worker.is_running():
        raise HTTPException(
            status_code=409, detail="An indexing job is already running"
        )

    options = ReprocessOptions(
        scope=payload.scope,
        source_ids=payload.source_ids,
        status=payload.status,
        rebuild_chunks=payload.rebuild_chunks,
        rebuild_embeddings=payload.rebuild_embeddings,
        reclassify_document_types=payload.reclassify_document_types,
        recalculate_content_hints=payload.recalculate_content_hints,
        remove_boilerplate=payload.remove_boilerplate,
        invalidate_caches=payload.invalidate_caches,
        limit=payload.limit,
        dry_run=payload.dry_run,
        needs_reprocess_only=payload.needs_reprocess_only,
    )

    if payload.dry_run:
        settings = SettingsRepository(db).get_or_create()
        from app.services.reprocess_service import ReprocessService

        preview = ReprocessService(db, settings).preview(options)
        return ReprocessExistingResponse(
            job_id="dry-run",
            status="preview",
            selected_sources=preview.selected_sources,
            estimated_chunks=preview.estimated_chunks,
            sample_boilerplate_ratios=preview.sample_boilerplate_ratios,
        )

    job_id = reprocess_worker.start(options)
    settings = SettingsRepository(db).get_or_create()
    from app.services.reprocess_service import ReprocessService

    selected = ReprocessService(db, settings).preview(options).selected_sources
    return ReprocessExistingResponse(
        job_id=str(job_id),
        status="started",
        selected_sources=selected,
    )


@router.post("/generate-source-intelligence", response_model=GenerateSourceIntelligenceResponse)
def generate_source_intelligence(
    payload: GenerateSourceIntelligenceRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> GenerateSourceIntelligenceResponse:
    if source_intelligence_worker.is_running():
        raise HTTPException(
            status_code=409, detail="A Source Intelligence job is already running"
        )
    if reprocess_worker.is_running():
        raise HTTPException(
            status_code=409, detail="A reprocess job is already running"
        )
    if indexing_worker.is_running():
        raise HTTPException(
            status_code=409, detail="An indexing job is already running"
        )

    settings = SettingsRepository(db).get_or_create()
    service = SourceIntelligenceGenerationService(db, settings)
    options = IntelligenceOptions(
        scope=payload.scope,
        source_ids=payload.source_ids,
        limit=payload.limit,
        dry_run=payload.dry_run,
        generate_summaries=payload.generate_summaries,
    )
    selected = service.count_sources(options)
    if selected <= 0 and not payload.dry_run:
        if payload.scope == "needs_intelligence":
            raise HTTPException(
                status_code=409,
                detail=(
                    "No sources need intelligence updates. "
                    "Use scope=all (Reprocess all sources) to rebuild profiles."
                ),
            )
        raise HTTPException(status_code=409, detail="No indexed sources matched the request.")
    job_id = source_intelligence_worker.start(options)
    return GenerateSourceIntelligenceResponse(
        job_id=str(job_id),
        status="started" if not payload.dry_run else "preview_started",
        selected_sources=selected,
    )


@router.get("/source-intelligence-stats")
def source_intelligence_stats(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> dict:
    from sqlalchemy import func, select

    from app.services.source_intelligence_generation_service import (
        IntelligenceOptions,
        SourceIntelligenceGenerationService,
    )

    settings = SettingsRepository(db).get_or_create()
    svc = SourceIntelligenceGenerationService(db, settings)
    needs = svc.count_sources(IntelligenceOptions(scope="needs_intelligence"))
    total_indexed = int(
        db.scalar(select(func.count()).select_from(Source).where(Source.status == "indexed")) or 0
    )
    up_to_date = max(0, total_indexed - needs)
    perf = svc._perf_settings()
    llm_on = bool(getattr(settings, "enable_llm_source_intelligence", True))
    return {
        "sources_needing_intelligence": needs,
        "sources_up_to_date": up_to_date,
        "total_indexed": total_indexed,
        "estimated_llm_calls": needs if llm_on else 0,
        "estimated_skips": 0,
        "worker_count": svc._resolve_worker_count(),
        "batch_size": perf["db_batch_size"],
        "page_size": perf["page_size"],
        "llm_enabled": llm_on,
    }


@router.get("/status", response_model=IndexJobStatus)
def index_status(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> IndexJobStatus:
    import time

    global _stale_job_healed_at  # noqa: PLW0603

    repo = IndexJobRepository(db)
    job: IndexJob | None = None
    if source_intelligence_worker.is_running():
        worker_state = source_intelligence_worker.status()
        if worker_state.job_id:
            job = repo.get(worker_state.job_id)
    if job is None and reprocess_worker.is_running():
        worker_state = reprocess_worker.status()
        if worker_state.job_id:
            job = repo.get(worker_state.job_id)
    if job is None and indexing_worker.is_running():
        job_id = getattr(indexing_worker, "_current_job_id", None)
        if job_id:
            job = repo.get(job_id)
    if job is None:
        job = repo.latest()

    # Heal orphaned "running" jobs at most once per minute (not on every poll).
    if (
        job is not None
        and job.status == "running"
        and not source_intelligence_worker.is_running()
        and not reprocess_worker.is_running()
        and not indexing_worker.is_running()
    ):
        now = time.monotonic()
        if _stale_job_healed_at is None or (now - _stale_job_healed_at) > 60:
            job.status = "failed"
            job.current_phase = "failed"
            if job.finished_at is None:
                job.finished_at = utcnow()
            repo.save(job)
            queue_preview_cache.invalidate()
            _stale_job_healed_at = now

    return job_to_status(job)


@router.get("/queue-preview", response_model=IndexQueuePreview)
def queue_preview(
    db: Session = Depends(get_db),
    _user=Depends(require_operator),
) -> IndexQueuePreview:
    settings = SettingsRepository(db).get_or_create()
    page_types = {"page", "html"}
    max_pages = 0 if settings.scan_all_pages else settings.max_pages_per_run
    cache_key = (
        settings.indexed_page_refresh_interval_hours,
        settings.indexed_file_refresh_interval_hours,
        max_pages,
        tuple(sorted(page_types)),
    )
    cached = queue_preview_cache.get(cache_key)
    if cached is not None:
        return preview_to_response(cached)

    data = SourceRepository(db).queue_preview(
        page_refresh_hours=settings.indexed_page_refresh_interval_hours,
        file_refresh_hours=settings.indexed_file_refresh_interval_hours,
        max_pages_per_run=max_pages,
        source_types=page_types,
    )
    queue_preview_cache.set(cache_key, data)
    return preview_to_response(data)
