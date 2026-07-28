"""Settings API: read and update agent configuration."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_authenticated
from app.core.database import get_db
from app.models.settings import Settings
from app.repositories.settings_repository import SettingsRepository
from app.schemas.chat import CacheClearResponse
from app.schemas.settings import (
    MemoryVersionBumpRequest,
    MemoryVersionBumpResponse,
    SettingsRead,
    SettingsUpdate,
)
from app.services.cache_invalidation_service import CacheInvalidationService
from app.services.memory_version_service import MemoryVersionService

router = APIRouter(prefix="/api/settings", tags=["settings"])

_RETRIEVAL_SETTING_FIELDS = (
    "top_k",
    "similarity_threshold",
    "retrieval_mode",
    "enable_query_expansion",
    "enable_reranking",
    "enable_intent_aware_retrieval",
    "enable_canonical_source_selection",
    "enable_broad_question_mode",
    "enable_context_builder",
    "retrieval_candidate_count",
    "max_pages_in_context",
    "max_chunks_per_page",
    "embedding_model",
    "qdrant_collection",
    "enable_retrieval_cache",
    "retrieval_cache_ttl_seconds",
)


def _snapshot_retrieval_settings(settings: Settings) -> dict:
    return {name: getattr(settings, name, None) for name in _RETRIEVAL_SETTING_FIELDS}


def _retrieval_settings_changed(before: dict, after: SettingsUpdate) -> bool:
    payload = after.model_dump()
    for name in _RETRIEVAL_SETTING_FIELDS:
        if name in payload and payload[name] != before.get(name):
            return True
    return False


def _to_read(model: Settings) -> SettingsRead:
    return SettingsRead(
        id=model.id,
        site_url=model.site_url,
        sitemap_url=model.sitemap_url,
        crawl_depth=model.crawl_depth,
        allowed_domains=json.loads(model.allowed_domains_json or "[]"),
        deny_url_patterns=json.loads(model.deny_url_patterns_json or "[]"),
        allowed_file_types=json.loads(model.allowed_file_types_json or "[]"),
        scan_mode=model.scan_mode,
        enable_file_indexing=model.enable_file_indexing,
        scan_all_pages=model.scan_all_pages,
        scan_all_files=model.scan_all_files,
        llm_model=model.llm_model,
        embedding_model=model.embedding_model,
        qdrant_collection=model.qdrant_collection,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        top_k=model.top_k,
        similarity_threshold=model.similarity_threshold,
        temperature=model.temperature,
        max_tokens=model.max_tokens,
        system_prompt=model.system_prompt,
        fallback_answer=model.fallback_answer,
        enable_sources=model.enable_sources,
        enable_chat_logs=model.enable_chat_logs,
        request_timeout_seconds=model.request_timeout_seconds,
        max_pages_per_run=model.max_pages_per_run,
        max_files_per_run=model.max_files_per_run,
        indexed_page_refresh_interval_hours=model.indexed_page_refresh_interval_hours,
        indexed_file_refresh_interval_hours=model.indexed_file_refresh_interval_hours,
        default_response_language=model.default_response_language,
        dashboard_language=model.dashboard_language,
        enable_source_links=model.enable_source_links,
        enable_reranking=model.enable_reranking,
        enable_ukrainian_polish_pass=model.enable_ukrainian_polish_pass,
        fast_mode_enabled=model.fast_mode_enabled,
        enable_retrieval_cache=model.enable_retrieval_cache,
        enable_semantic_answer_cache=model.enable_semantic_answer_cache,
        retrieval_cache_ttl_seconds=model.retrieval_cache_ttl_seconds,
        answer_cache_ttl_seconds=model.answer_cache_ttl_seconds,
        semantic_cache_similarity_threshold=model.semantic_cache_similarity_threshold,
        max_cached_answers=model.max_cached_answers,
        knowledge_version=model.knowledge_version,
        memory_version=getattr(model, "memory_version", 1),
        retrieval_mode=model.retrieval_mode,
        homepage_boost_enabled=model.homepage_boost_enabled,
        title_match_boost=model.title_match_boost,
        heading_match_boost=model.heading_match_boost,
        homepage_boost_value=model.homepage_boost_value,
        short_query_lexical_boost=model.short_query_lexical_boost,
        enable_query_expansion=model.enable_query_expansion,
        enable_retrieval_debug=model.enable_retrieval_debug,
        enable_intent_aware_retrieval=model.enable_intent_aware_retrieval,
        enable_canonical_source_selection=model.enable_canonical_source_selection,
        enable_news_deprioritization_for_overview_queries=model.enable_news_deprioritization_for_overview_queries,
        fallback_second_pass_enabled=model.fallback_second_pass_enabled,
        enable_tracing=model.enable_tracing,
        enable_trace_storage=model.enable_trace_storage,
        enable_request_metadata_logging=model.enable_request_metadata_logging,
        enable_chat_debug_payload=model.enable_chat_debug_payload,
        enable_semantic_diagnostics_v2=getattr(
            model, "enable_semantic_diagnostics_v2", False
        ),
        cache_namespace_v2_enabled=getattr(model, "cache_namespace_v2_enabled", False),
        memory_shadow_write_enabled=getattr(model, "memory_shadow_write_enabled", False),
        memory_evidence_assist_enabled=getattr(
            model, "memory_evidence_assist_enabled", False
        ),
        memory_canonical_shadow_enabled=getattr(
            model, "memory_canonical_shadow_enabled", False
        ),
        max_trace_retention_days=model.max_trace_retention_days,
        max_concurrent_chat_requests=model.max_concurrent_chat_requests,
        max_concurrent_llm_requests=model.max_concurrent_llm_requests,
        max_concurrent_embedding_requests=model.max_concurrent_embedding_requests,
        max_concurrent_background_embedding_requests=getattr(
            model, "max_concurrent_background_embedding_requests", 1
        ),
        chat_total_timeout_seconds=model.chat_total_timeout_seconds,
        ollama_generation_timeout_seconds=model.ollama_generation_timeout_seconds,
        ollama_embedding_timeout_seconds=model.ollama_embedding_timeout_seconds,
        qdrant_timeout_seconds=model.qdrant_timeout_seconds,
        polish_mode=getattr(model, "polish_mode", "off"),
        polish_min_answer_chars=getattr(model, "polish_min_answer_chars", 2000),
        polish_timeout_seconds=getattr(model, "polish_timeout_seconds", 20),
        polish_model=getattr(model, "polish_model", ""),
        polish_skip_if_generation_ms_over=getattr(model, "polish_skip_if_generation_ms_over", 25000),
        llm_num_predict=getattr(model, "llm_num_predict", 512),
        llm_num_ctx_mode=getattr(model, "llm_num_ctx_mode", "auto"),
        llm_fixed_num_ctx=getattr(model, "llm_fixed_num_ctx", 4096),
        llm_max_prompt_chars=getattr(model, "llm_max_prompt_chars", 8000),
        llm_keep_alive=getattr(model, "llm_keep_alive", "30m"),
        llm_mode_profile=getattr(model, "llm_mode_profile", "balanced"),
        enable_llm_warmup=getattr(model, "enable_llm_warmup", True),
        max_sources_in_prompt=getattr(model, "max_sources_in_prompt", 2),
        max_chars_per_source=getattr(model, "max_chars_per_source", 800),
        max_total_context_chars=getattr(model, "max_total_context_chars", 2500),
        max_semantic_expansions=getattr(model, "max_semantic_expansions", 5),
        context_builder_mode=getattr(model, "context_builder_mode", "full_content"),
        max_context_tokens=getattr(model, "max_context_tokens", 2048),
        chunk_merge_enabled=getattr(model, "chunk_merge_enabled", True),
        ranking_freshness_weight=getattr(model, "ranking_freshness_weight", 0.05),
        enable_chat_streaming=getattr(model, "enable_chat_streaming", True),
        llm_retry_max_attempts=getattr(model, "llm_retry_max_attempts", 1),
        llm_retry_on_timeout_only=getattr(model, "llm_retry_on_timeout_only", True),
        prefer_user_language_sources=getattr(model, "prefer_user_language_sources", True),
        enable_source_intelligence=getattr(model, "enable_source_intelligence", True),
        enable_llm_source_intelligence=getattr(model, "enable_llm_source_intelligence", True),
        source_intelligence_importance_threshold=getattr(
            model, "source_intelligence_importance_threshold", 70
        ),
        penalize_campaigns_for_overview=getattr(model, "penalize_campaigns_for_overview", True),
        source_intelligence_db_batch_size=getattr(model, "source_intelligence_db_batch_size", 50),
        source_intelligence_page_size=getattr(model, "source_intelligence_page_size", 100),
        source_intelligence_worker_count=getattr(model, "source_intelligence_worker_count", 0),
        source_intelligence_progress_flush_every_sources=getattr(
            model, "source_intelligence_progress_flush_every_sources", 10
        ),
        source_intelligence_progress_flush_interval_seconds=getattr(
            model, "source_intelligence_progress_flush_interval_seconds", 3
        ),
        source_intelligence_cache_invalidation_mode=getattr(
            model, "source_intelligence_cache_invalidation_mode", "version_bump_only"
        ),
        run_source_intelligence_inline_during_indexing=getattr(
            model, "run_source_intelligence_inline_during_indexing", False
        ),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=SettingsRead)
def get_settings(
    db: Session = Depends(get_db),
    _user=Depends(require_authenticated),
) -> SettingsRead:
    settings = SettingsRepository(db).get_or_create()
    return _to_read(settings)


@router.put("", response_model=SettingsRead)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> SettingsRead:
    repo = SettingsRepository(db)
    settings = repo.get_or_create()
    before = _snapshot_retrieval_settings(settings)

    settings.site_url = payload.site_url
    settings.sitemap_url = payload.sitemap_url
    settings.crawl_depth = payload.crawl_depth
    settings.allowed_domains_json = json.dumps(payload.allowed_domains)
    settings.deny_url_patterns_json = json.dumps(payload.deny_url_patterns)
    settings.allowed_file_types_json = json.dumps(payload.allowed_file_types)
    settings.scan_mode = payload.scan_mode
    settings.enable_file_indexing = payload.enable_file_indexing
    settings.scan_all_pages = payload.scan_all_pages
    settings.scan_all_files = payload.scan_all_files
    settings.llm_model = payload.llm_model
    settings.embedding_model = payload.embedding_model
    settings.qdrant_collection = payload.qdrant_collection
    settings.chunk_size = payload.chunk_size
    settings.chunk_overlap = payload.chunk_overlap
    settings.top_k = payload.top_k
    settings.similarity_threshold = payload.similarity_threshold
    settings.temperature = payload.temperature
    settings.max_tokens = payload.max_tokens
    settings.system_prompt = payload.system_prompt
    settings.fallback_answer = payload.fallback_answer
    settings.enable_sources = payload.enable_sources
    settings.enable_chat_logs = payload.enable_chat_logs
    settings.request_timeout_seconds = payload.request_timeout_seconds
    settings.max_pages_per_run = payload.max_pages_per_run
    settings.max_files_per_run = payload.max_files_per_run
    settings.indexed_page_refresh_interval_hours = payload.indexed_page_refresh_interval_hours
    settings.indexed_file_refresh_interval_hours = payload.indexed_file_refresh_interval_hours
    settings.default_response_language = payload.default_response_language
    settings.dashboard_language = payload.dashboard_language
    settings.enable_source_links = payload.enable_source_links
    settings.enable_reranking = payload.enable_reranking
    settings.enable_ukrainian_polish_pass = payload.enable_ukrainian_polish_pass
    settings.fast_mode_enabled = payload.fast_mode_enabled
    settings.enable_retrieval_cache = payload.enable_retrieval_cache
    settings.enable_semantic_answer_cache = payload.enable_semantic_answer_cache
    settings.retrieval_cache_ttl_seconds = payload.retrieval_cache_ttl_seconds
    settings.answer_cache_ttl_seconds = payload.answer_cache_ttl_seconds
    settings.semantic_cache_similarity_threshold = (
        payload.semantic_cache_similarity_threshold
    )
    settings.max_cached_answers = payload.max_cached_answers
    settings.retrieval_mode = payload.retrieval_mode
    settings.homepage_boost_enabled = payload.homepage_boost_enabled
    settings.title_match_boost = payload.title_match_boost
    settings.heading_match_boost = payload.heading_match_boost
    settings.homepage_boost_value = payload.homepage_boost_value
    settings.short_query_lexical_boost = payload.short_query_lexical_boost
    settings.enable_query_expansion = payload.enable_query_expansion
    settings.enable_retrieval_debug = payload.enable_retrieval_debug
    settings.enable_intent_aware_retrieval = payload.enable_intent_aware_retrieval
    settings.enable_canonical_source_selection = payload.enable_canonical_source_selection
    settings.enable_news_deprioritization_for_overview_queries = (
        payload.enable_news_deprioritization_for_overview_queries
    )
    settings.fallback_second_pass_enabled = payload.fallback_second_pass_enabled
    settings.enable_broad_question_mode = payload.enable_broad_question_mode
    settings.enable_context_builder = payload.enable_context_builder
    settings.retrieval_candidate_count = payload.retrieval_candidate_count
    settings.max_pages_in_context = payload.max_pages_in_context
    settings.max_chunks_per_page = payload.max_chunks_per_page
    settings.polish_mode = payload.polish_mode
    settings.polish_min_answer_chars = payload.polish_min_answer_chars
    settings.polish_timeout_seconds = payload.polish_timeout_seconds
    settings.polish_model = payload.polish_model
    settings.polish_skip_if_generation_ms_over = payload.polish_skip_if_generation_ms_over
    settings.llm_num_predict = payload.llm_num_predict
    settings.llm_num_ctx_mode = payload.llm_num_ctx_mode
    settings.llm_fixed_num_ctx = payload.llm_fixed_num_ctx
    settings.llm_max_prompt_chars = payload.llm_max_prompt_chars
    settings.llm_keep_alive = payload.llm_keep_alive
    settings.llm_mode_profile = payload.llm_mode_profile
    settings.enable_llm_warmup = payload.enable_llm_warmup
    settings.max_sources_in_prompt = payload.max_sources_in_prompt
    settings.max_chars_per_source = payload.max_chars_per_source
    settings.max_total_context_chars = payload.max_total_context_chars
    settings.max_semantic_expansions = payload.max_semantic_expansions
    settings.context_builder_mode = payload.context_builder_mode
    settings.max_context_tokens = payload.max_context_tokens
    settings.chunk_merge_enabled = payload.chunk_merge_enabled
    settings.ranking_freshness_weight = payload.ranking_freshness_weight
    settings.enable_chat_streaming = payload.enable_chat_streaming
    settings.llm_retry_max_attempts = payload.llm_retry_max_attempts
    settings.llm_retry_on_timeout_only = payload.llm_retry_on_timeout_only
    settings.prefer_user_language_sources = payload.prefer_user_language_sources
    settings.enable_source_intelligence = payload.enable_source_intelligence
    settings.enable_llm_source_intelligence = payload.enable_llm_source_intelligence
    settings.source_intelligence_importance_threshold = payload.source_intelligence_importance_threshold
    settings.penalize_campaigns_for_overview = payload.penalize_campaigns_for_overview
    settings.source_intelligence_db_batch_size = payload.source_intelligence_db_batch_size
    settings.source_intelligence_page_size = payload.source_intelligence_page_size
    settings.source_intelligence_worker_count = payload.source_intelligence_worker_count
    settings.source_intelligence_progress_flush_every_sources = (
        payload.source_intelligence_progress_flush_every_sources
    )
    settings.source_intelligence_progress_flush_interval_seconds = (
        payload.source_intelligence_progress_flush_interval_seconds
    )
    settings.source_intelligence_cache_invalidation_mode = (
        payload.source_intelligence_cache_invalidation_mode
    )
    settings.run_source_intelligence_inline_during_indexing = (
        payload.run_source_intelligence_inline_during_indexing
    )
    settings.enable_tracing = payload.enable_tracing
    settings.enable_trace_storage = payload.enable_trace_storage
    settings.enable_request_metadata_logging = payload.enable_request_metadata_logging
    settings.enable_chat_debug_payload = payload.enable_chat_debug_payload
    settings.enable_semantic_diagnostics_v2 = payload.enable_semantic_diagnostics_v2
    settings.cache_namespace_v2_enabled = payload.cache_namespace_v2_enabled
    settings.memory_shadow_write_enabled = payload.memory_shadow_write_enabled
    settings.memory_evidence_assist_enabled = payload.memory_evidence_assist_enabled
    settings.memory_canonical_shadow_enabled = payload.memory_canonical_shadow_enabled
    settings.max_trace_retention_days = payload.max_trace_retention_days
    settings.max_concurrent_chat_requests = payload.max_concurrent_chat_requests
    settings.max_concurrent_llm_requests = payload.max_concurrent_llm_requests
    settings.max_concurrent_embedding_requests = payload.max_concurrent_embedding_requests
    settings.max_concurrent_background_embedding_requests = (
        payload.max_concurrent_background_embedding_requests
    )
    settings.chat_total_timeout_seconds = payload.chat_total_timeout_seconds
    settings.ollama_generation_timeout_seconds = payload.ollama_generation_timeout_seconds
    settings.ollama_embedding_timeout_seconds = payload.ollama_embedding_timeout_seconds
    settings.qdrant_timeout_seconds = payload.qdrant_timeout_seconds

    settings = repo.save(settings)
    if _retrieval_settings_changed(before, payload):
        CacheInvalidationService(db, settings).invalidate_retrieval_cache(
            "retrieval_settings_updated"
        )
    return _to_read(settings)


@router.post("/cache/clear-retrieval", response_model=CacheClearResponse)
def clear_retrieval_cache(
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> CacheClearResponse:
    rows = CacheInvalidationService(db).invalidate_retrieval_cache("manual_clear")
    return CacheClearResponse(cleared_retrieval_rows=rows, reason="manual_clear")


@router.post("/cache/clear-answer", response_model=CacheClearResponse)
def clear_answer_cache(
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> CacheClearResponse:
    CacheInvalidationService(db).invalidate_answer_cache("manual_clear")
    return CacheClearResponse(cleared_answer_cache=True, reason="manual_clear")


@router.post("/cache/clear-all", response_model=CacheClearResponse)
def clear_all_caches(
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> CacheClearResponse:
    rows = CacheInvalidationService(db).invalidate_all_caches("manual_clear")
    return CacheClearResponse(
        cleared_retrieval_rows=rows,
        cleared_answer_cache=True,
        reason="manual_clear",
    )


@router.post("/memory-version/bump", response_model=MemoryVersionBumpResponse)
def bump_memory_version(
    body: MemoryVersionBumpRequest | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
) -> MemoryVersionBumpResponse:
    """Manual admin stub to bump epistemic memory version (Release 0.3).

    Does not invalidate caches until cache namespace v2 (Step 023+).
    When ``memory_shadow_write_enabled`` is true, shadow claim integration auto-bumps
    via ``EpistemicMemoryIntegrationService`` (Step 031). Manual ops use this endpoint.
    """
    svc = MemoryVersionService(db)
    previous = svc.get()
    new_version = svc.bump()
    reason = (body.reason.strip() if body and body.reason else "") or "manual_admin_stub"
    return MemoryVersionBumpResponse(
        previous_memory_version=previous,
        new_memory_version=new_version,
        reason=reason,
    )
