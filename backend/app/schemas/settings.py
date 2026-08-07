"""Pydantic schemas for agent settings."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScanMode = Literal["pages_only", "pages_and_files", "files_only"]
RetrievalMode = Literal["dense", "lexical", "hybrid"]
DashboardLanguage = Literal["uk", "en"]


class SettingsBase(BaseModel):
    site_url: str | None = None
    sitemap_url: str | None = None
    crawl_depth: int = Field(default=2, ge=0, le=10)
    allowed_domains: list[str] = Field(default_factory=list)
    deny_url_patterns: list[str] = Field(default_factory=list)
    allowed_file_types: list[str] = Field(
        default_factory=lambda: ["pdf", "docx", "txt"]
    )

    # Scan behaviour.
    scan_mode: ScanMode = "pages_only"
    enable_file_indexing: bool = False
    scan_all_pages: bool = False
    scan_all_files: bool = False

    llm_model: str = "qwen2.5:3b"
    embedding_model: str = "bge-m3"
    qdrant_collection: str = "site_knowledge"

    chunk_size: int = Field(default=800, ge=100, le=8000)
    chunk_overlap: int = Field(default=120, ge=0, le=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=32000)

    system_prompt: str = ""
    fallback_answer: str = "Вибачте, у мене немає такої інформації."

    enable_sources: bool = True
    enable_chat_logs: bool = True

    request_timeout_seconds: int = Field(default=30, ge=1, le=600)
    # 0 means unlimited (or use scan_all_pages / scan_all_files).
    max_pages_per_run: int = Field(default=200, ge=0, le=1000000)
    max_files_per_run: int = Field(default=100, ge=0, le=1000000)
    indexed_page_refresh_interval_hours: int = Field(default=168, ge=1, le=8760)
    indexed_file_refresh_interval_hours: int = Field(default=168, ge=1, le=8760)

    # --- Answer quality / performance / caching ---
    default_response_language: str = "uk"
    dashboard_language: DashboardLanguage = "uk"
    enable_source_links: bool = True
    enable_reranking: bool = True
    enable_ukrainian_polish_pass: bool = False
    fast_mode_enabled: bool = False
    polish_mode: str = "off"
    polish_min_answer_chars: int = Field(default=2000, ge=0, le=20000)
    polish_timeout_seconds: int = Field(default=15, ge=5, le=120)
    polish_model: str = ""
    polish_skip_if_generation_ms_over: int = Field(default=15000, ge=0, le=300000)
    llm_num_predict: int = Field(default=320, ge=64, le=4096)
    llm_num_ctx_mode: str = "auto"
    llm_fixed_num_ctx: int = Field(default=4096, ge=2048, le=32768)
    llm_max_prompt_chars: int = Field(default=4500, ge=1000, le=64000)
    llm_keep_alive: str = "30m"
    llm_mode_profile: str = "fast"
    enable_llm_warmup: bool = True
    max_sources_in_prompt: int = Field(default=2, ge=1, le=10)
    max_chars_per_source: int = Field(default=800, ge=200, le=8000)
    max_total_context_chars: int = Field(default=2500, ge=500, le=32000)
    max_semantic_expansions: int = Field(default=5, ge=1, le=10)
    context_builder_mode: str = "full_content"
    max_context_tokens: int = Field(default=2048, ge=256, le=16000)
    chunk_merge_enabled: bool = True
    ranking_freshness_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    enable_chat_streaming: bool = True
    llm_retry_max_attempts: int = Field(default=1, ge=0, le=3)
    llm_retry_on_timeout_only: bool = True
    prefer_user_language_sources: bool = True
    enable_source_intelligence: bool = True
    enable_llm_source_intelligence: bool = True
    enable_knowledge_understanding: bool = False
    source_intelligence_importance_threshold: int = Field(default=70, ge=0, le=100)
    penalize_campaigns_for_overview: bool = True
    source_intelligence_db_batch_size: int = Field(default=50, ge=1, le=500)
    source_intelligence_page_size: int = Field(default=100, ge=10, le=1000)
    source_intelligence_worker_count: int = Field(default=0, ge=0, le=16)
    source_intelligence_progress_flush_every_sources: int = Field(default=10, ge=1, le=500)
    source_intelligence_progress_flush_interval_seconds: int = Field(default=3, ge=1, le=120)
    source_intelligence_cache_invalidation_mode: str = "version_bump_only"
    run_source_intelligence_inline_during_indexing: bool = False

    enable_retrieval_cache: bool = True
    enable_semantic_answer_cache: bool = True
    retrieval_cache_ttl_seconds: int = Field(default=3600, ge=0, le=2592000)
    answer_cache_ttl_seconds: int = Field(default=86400, ge=0, le=2592000)
    semantic_cache_similarity_threshold: float = Field(
        default=0.93, ge=0.0, le=1.0
    )
    max_cached_answers: int = Field(default=5000, ge=0, le=1000000)

    # --- Retrieval quality tuning ---
    retrieval_mode: RetrievalMode = "hybrid"
    # Step 052: title/heading/homepage/short_query boost knobs removed from the
    # Settings API contract. ORM columns remain; DocumentScorer / RPS / cache NS
    # still read stored values. Legacy PUT bodies are ignored via extra="ignore".
    enable_query_expansion: bool = True
    enable_retrieval_debug: bool = False

    enable_intent_aware_retrieval: bool = True
    enable_canonical_source_selection: bool = True
    enable_news_deprioritization_for_overview_queries: bool = True
    fallback_second_pass_enabled: bool = True

    enable_broad_question_mode: bool = True
    enable_context_builder: bool = True
    retrieval_candidate_count: int = Field(default=30, ge=5, le=100)
    max_pages_in_context: int = Field(default=3, ge=1, le=10)
    max_chunks_per_page: int = Field(default=2, ge=1, le=20)

    # Document-first retrieval engine
    retrieval_profile: str = Field(default="automatic")
    document_priorities_json: str = ""
    intent_profiles_json: str = ""
    scoring_weights_json: str = ""
    top_k_dense: int | None = Field(default=None, ge=5, le=100)
    top_k_lexical: int | None = Field(default=None, ge=5, le=100)
    rerank_limit: int | None = Field(default=None, ge=3, le=50)
    document_limit: int | None = Field(default=None, ge=1, le=20)
    minimum_retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # Tracing / observability / production limits.
    enable_tracing: bool = True
    enable_trace_storage: bool = True
    enable_request_metadata_logging: bool = True
    enable_chat_debug_payload: bool = True
    enable_semantic_diagnostics_v2: bool = True
    cache_namespace_v2_enabled: bool = True
    memory_shadow_write_enabled: bool = True
    memory_evidence_assist_enabled: bool = True
    memory_canonical_shadow_enabled: bool = True
    allow_legacy_kp_presets: bool = False
    legacy_doc_type_canonical_enabled: bool = False
    max_trace_retention_days: int = Field(default=30, ge=1, le=3650)

    max_concurrent_chat_requests: int = Field(default=20, ge=1, le=1000)
    max_concurrent_llm_requests: int = Field(default=2, ge=1, le=100)
    max_concurrent_embedding_requests: int = Field(default=2, ge=1, le=100)
    max_concurrent_background_embedding_requests: int = Field(default=1, ge=1, le=100)

    chat_total_timeout_seconds: int = Field(default=120, ge=5, le=600)
    ollama_generation_timeout_seconds: int = Field(default=60, ge=5, le=600)
    ollama_embedding_timeout_seconds: int = Field(default=30, ge=5, le=300)
    qdrant_timeout_seconds: int = Field(default=30, ge=5, le=300)


class SettingsUpdate(SettingsBase):
    """All fields optional on update."""

    model_config = ConfigDict(extra="ignore")


class SettingsRead(SettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_version: int | None = None
    memory_version: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MemoryVersionBumpRequest(BaseModel):
    """Optional operator note for manual memory version bumps (Step 022 stub)."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional note recorded in the response; not persisted.",
    )


class MemoryVersionBumpResponse(BaseModel):
    previous_memory_version: int
    new_memory_version: int
    reason: str
