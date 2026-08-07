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
from app.services.system_prompt_defaults import DEFAULT_SYSTEM_PROMPT

router = APIRouter(prefix="/api/settings", tags=["settings"])

_RETRIEVAL_SETTING_FIELDS = (
    "top_k",
    "similarity_threshold",
    "retrieval_mode",
    "enable_query_expansion",
    "enable_reranking",
    "enable_intent_aware_retrieval",
    "enable_canonical_source_selection",
    "legacy_doc_type_canonical_enabled",
    "enable_broad_question_mode",
    "enable_context_builder",
    "retrieval_candidate_count",
    "max_pages_in_context",
    "max_chunks_per_page",
    "retrieval_profile",
    "top_k_dense",
    "top_k_lexical",
    "rerank_limit",
    "document_limit",
    "minimum_retrieval_score",
    "embedding_model",
    "qdrant_collection",
    "enable_retrieval_cache",
    "retrieval_cache_ttl_seconds",
)


def _snapshot_retrieval_settings(settings: Settings) -> dict:
    return {name: getattr(settings, name, None) for name in _RETRIEVAL_SETTING_FIELDS}


def _retrieval_settings_changed(before: dict, after: SettingsUpdate) -> bool:
    # Only fields the client actually sent — partial PUTs must not look like
    # "every default changed" when unset keys are filled by SettingsBase defaults.
    payload = after.model_dump(exclude_unset=True)
    for name in _RETRIEVAL_SETTING_FIELDS:
        if name in payload and payload[name] != before.get(name):
            return True
    return False


# API list fields ↔ ORM JSON columns (same mapping as full PUT historically).
_SETTINGS_JSON_LIST_FIELDS = {
    "allowed_domains": "allowed_domains_json",
    "deny_url_patterns": "deny_url_patterns_json",
    "allowed_file_types": "allowed_file_types_json",
}

# Direct ORM attributes writable via SettingsUpdate. Keep in sync with the
# historical full-PUT assign list (do not auto-setattr every schema field —
# some SettingsBase keys are not wired through this endpoint yet).
_SETTINGS_DIRECT_FIELDS = (
    "site_url",
    "sitemap_url",
    "crawl_depth",
    "scan_mode",
    "enable_file_indexing",
    "scan_all_pages",
    "scan_all_files",
    "llm_model",
    "embedding_model",
    "qdrant_collection",
    "chunk_size",
    "chunk_overlap",
    "top_k",
    "similarity_threshold",
    "temperature",
    "max_tokens",
    "system_prompt",
    "fallback_answer",
    "enable_sources",
    "enable_chat_logs",
    "request_timeout_seconds",
    "max_pages_per_run",
    "max_files_per_run",
    "indexed_page_refresh_interval_hours",
    "indexed_file_refresh_interval_hours",
    "default_response_language",
    "dashboard_language",
    "enable_source_links",
    "enable_reranking",
    "enable_ukrainian_polish_pass",
    "fast_mode_enabled",
    "enable_retrieval_cache",
    "enable_semantic_answer_cache",
    "retrieval_cache_ttl_seconds",
    "answer_cache_ttl_seconds",
    "semantic_cache_similarity_threshold",
    "max_cached_answers",
    "retrieval_mode",
    "enable_query_expansion",
    "enable_retrieval_debug",
    "enable_intent_aware_retrieval",
    "enable_canonical_source_selection",
    "enable_news_deprioritization_for_overview_queries",
    "fallback_second_pass_enabled",
    "enable_broad_question_mode",
    "enable_context_builder",
    "retrieval_candidate_count",
    "max_pages_in_context",
    "max_chunks_per_page",
    "retrieval_profile",
    "top_k_dense",
    "top_k_lexical",
    "rerank_limit",
    "document_limit",
    "minimum_retrieval_score",
    "polish_mode",
    "polish_min_answer_chars",
    "polish_timeout_seconds",
    "polish_model",
    "polish_skip_if_generation_ms_over",
    "llm_num_predict",
    "llm_num_ctx_mode",
    "llm_fixed_num_ctx",
    "llm_max_prompt_chars",
    "llm_keep_alive",
    "llm_mode_profile",
    "enable_llm_warmup",
    "max_sources_in_prompt",
    "max_chars_per_source",
    "max_total_context_chars",
    "max_semantic_expansions",
    "context_builder_mode",
    "max_context_tokens",
    "chunk_merge_enabled",
    "ranking_freshness_weight",
    "enable_chat_streaming",
    "llm_retry_max_attempts",
    "llm_retry_on_timeout_only",
    "prefer_user_language_sources",
    "enable_source_intelligence",
    "enable_llm_source_intelligence",
    "enable_knowledge_understanding",
    "source_intelligence_importance_threshold",
    "penalize_campaigns_for_overview",
    "source_intelligence_db_batch_size",
    "source_intelligence_page_size",
    "source_intelligence_worker_count",
    "source_intelligence_progress_flush_every_sources",
    "source_intelligence_progress_flush_interval_seconds",
    "source_intelligence_cache_invalidation_mode",
    "run_source_intelligence_inline_during_indexing",
    "enable_tracing",
    "enable_trace_storage",
    "enable_request_metadata_logging",
    "enable_chat_debug_payload",
    "enable_semantic_diagnostics_v2",
    "cache_namespace_v2_enabled",
    "memory_shadow_write_enabled",
    "memory_evidence_assist_enabled",
    "memory_canonical_shadow_enabled",
    "allow_legacy_kp_presets",
    "legacy_doc_type_canonical_enabled",
    "max_trace_retention_days",
    "max_concurrent_chat_requests",
    "max_concurrent_llm_requests",
    "max_concurrent_embedding_requests",
    "max_concurrent_background_embedding_requests",
    "chat_total_timeout_seconds",
    "ollama_generation_timeout_seconds",
    "ollama_embedding_timeout_seconds",
    "qdrant_timeout_seconds",
)


def _apply_settings_update(settings: Settings, payload: SettingsUpdate) -> None:
    """Apply only fields present in the request body (partial PUT safe)."""
    data = payload.model_dump(exclude_unset=True)
    for api_key, orm_key in _SETTINGS_JSON_LIST_FIELDS.items():
        if api_key in data:
            setattr(settings, orm_key, json.dumps(data[api_key]))
    for key in _SETTINGS_DIRECT_FIELDS:
        if key in data:
            setattr(settings, key, data[key])


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
        system_prompt=(model.system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT,
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
        enable_query_expansion=model.enable_query_expansion,
        enable_retrieval_debug=model.enable_retrieval_debug,
        enable_intent_aware_retrieval=model.enable_intent_aware_retrieval,
        enable_canonical_source_selection=model.enable_canonical_source_selection,
        enable_news_deprioritization_for_overview_queries=model.enable_news_deprioritization_for_overview_queries,
        fallback_second_pass_enabled=model.fallback_second_pass_enabled,
        enable_broad_question_mode=getattr(model, "enable_broad_question_mode", True),
        enable_context_builder=getattr(model, "enable_context_builder", True),
        retrieval_candidate_count=getattr(model, "retrieval_candidate_count", 30),
        max_pages_in_context=getattr(model, "max_pages_in_context", 3),
        max_chunks_per_page=getattr(model, "max_chunks_per_page", 2),
        retrieval_profile=getattr(model, "retrieval_profile", "automatic"),
        top_k_dense=getattr(model, "top_k_dense", None),
        top_k_lexical=getattr(model, "top_k_lexical", None),
        rerank_limit=getattr(model, "rerank_limit", None),
        document_limit=getattr(model, "document_limit", None),
        minimum_retrieval_score=getattr(model, "minimum_retrieval_score", None),
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
        allow_legacy_kp_presets=getattr(model, "allow_legacy_kp_presets", False),
        legacy_doc_type_canonical_enabled=getattr(
            model, "legacy_doc_type_canonical_enabled", False
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
        enable_knowledge_understanding=getattr(
            model, "enable_knowledge_understanding", False
        ),
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

    # Step 052: do not map deprecated boost fields from SettingsUpdate.
    # Legacy clients may still send them; SettingsUpdate(extra="ignore") drops them
    # so ORM homepage/title/heading/short_query boost columns stay unchanged.
    # Partial PUTs (Models / General) must only write fields actually sent.
    _apply_settings_update(settings, payload)

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
