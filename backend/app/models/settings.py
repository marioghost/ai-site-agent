"""Settings ORM model. Single-row table holding agent configuration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source / crawl configuration.
    site_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    sitemap_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    crawl_depth: Mapped[int] = mapped_column(Integer, default=2)
    allowed_domains_json: Mapped[str] = mapped_column(Text, default="[]")
    deny_url_patterns_json: Mapped[str] = mapped_column(Text, default="[]")
    allowed_file_types_json: Mapped[str] = mapped_column(
        Text, default='["pdf", "docx", "txt"]'
    )

    # Scan behaviour configuration.
    # scan_mode: pages_only | pages_and_files | files_only
    scan_mode: Mapped[str] = mapped_column(String(32), default="pages_only")
    enable_file_indexing: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_all_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_all_files: Mapped[bool] = mapped_column(Boolean, default=False)

    # Model configuration.
    llm_model: Mapped[str] = mapped_column(String(255), default="qwen2.5:3b")
    embedding_model: Mapped[str] = mapped_column(String(255), default="bge-m3")
    qdrant_collection: Mapped[str] = mapped_column(
        String(255), default="site_knowledge"
    )

    # Chunking / retrieval configuration.
    chunk_size: Mapped[int] = mapped_column(Integer, default=800)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=120)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.55)

    # Generation configuration.
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)

    system_prompt: Mapped[str] = mapped_column(Text, default="")
    fallback_answer: Mapped[str] = mapped_column(
        Text, default="Я не знайшов цієї інформації на сайті."
    )

    enable_sources: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_chat_logs: Mapped[bool] = mapped_column(Boolean, default=True)

    request_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_pages_per_run: Mapped[int] = mapped_column(Integer, default=200)
    max_files_per_run: Mapped[int] = mapped_column(Integer, default=100)
    indexed_page_refresh_interval_hours: Mapped[int] = mapped_column(Integer, default=168)
    indexed_file_refresh_interval_hours: Mapped[int] = mapped_column(Integer, default=168)

    # --- Answer quality / performance / caching ---
    default_response_language: Mapped[str] = mapped_column(String(8), default="uk")
    dashboard_language: Mapped[str] = mapped_column(String(8), default="uk")
    enable_source_links: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_reranking: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_ukrainian_polish_pass: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    fast_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    enable_retrieval_cache: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_semantic_answer_cache: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    retrieval_cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer, default=3600
    )
    answer_cache_ttl_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    semantic_cache_similarity_threshold: Mapped[float] = mapped_column(
        Float, default=0.93
    )
    max_cached_answers: Mapped[int] = mapped_column(Integer, default=5000)

    # Monotonic revision of the indexed knowledge; bumped when content changes.
    # Used to invalidate retrieval/answer caches safely.
    knowledge_version: Mapped[int] = mapped_column(Integer, default=1)

    # Monotonic revision of epistemic memory (claims, evidence); substrate for 0.3+ cache v2.
    # Not wired to cache invalidation until Release 0.3 Step 023+.
    memory_version: Mapped[int] = mapped_column(Integer, default=1)

    # --- Retrieval quality tuning ---
    # retrieval_mode: dense | lexical | hybrid
    retrieval_mode: Mapped[str] = mapped_column(String(16), default="hybrid")
    homepage_boost_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    title_match_boost: Mapped[float] = mapped_column(Float, default=0.15)
    heading_match_boost: Mapped[float] = mapped_column(Float, default=0.15)
    homepage_boost_value: Mapped[float] = mapped_column(Float, default=0.10)
    short_query_lexical_boost: Mapped[float] = mapped_column(Float, default=0.20)
    enable_query_expansion: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_retrieval_debug: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Broad-query / intent-aware retrieval ---
    enable_intent_aware_retrieval: Mapped[bool] = mapped_column(Boolean, default=True)
    # Deprecated: unused since semantic retrieval engine; column kept for DB compatibility.
    enable_document_type_boosting: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_canonical_source_selection: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_news_deprioritization_for_overview_queries: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    fallback_second_pass_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Advanced retrieval pipeline ---
    enable_broad_question_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    # Deprecated: unused since semantic retrieval engine; column kept for DB compatibility.
    enable_about_page_boost: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_context_builder: Mapped[bool] = mapped_column(Boolean, default=True)
    retrieval_candidate_count: Mapped[int] = mapped_column(Integer, default=30)
    max_pages_in_context: Mapped[int] = mapped_column(Integer, default=3)
    max_chunks_per_page: Mapped[int] = mapped_column(Integer, default=2)

    # --- LLM generation / polish ---
    polish_mode: Mapped[str] = mapped_column(String(16), default="off")
    polish_min_answer_chars: Mapped[int] = mapped_column(Integer, default=2000)
    polish_timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    polish_model: Mapped[str] = mapped_column(String(255), default="")
    polish_skip_if_generation_ms_over: Mapped[int] = mapped_column(Integer, default=15000)
    llm_num_predict: Mapped[int] = mapped_column(Integer, default=320)
    llm_num_ctx_mode: Mapped[str] = mapped_column(String(16), default="auto")
    llm_fixed_num_ctx: Mapped[int] = mapped_column(Integer, default=4096)
    llm_max_prompt_chars: Mapped[int] = mapped_column(Integer, default=4500)
    llm_keep_alive: Mapped[str] = mapped_column(String(64), default="30m")
    llm_mode_profile: Mapped[str] = mapped_column(String(32), default="fast")
    enable_llm_warmup: Mapped[bool] = mapped_column(Boolean, default=True)
    max_sources_in_prompt: Mapped[int] = mapped_column(Integer, default=2)
    max_chars_per_source: Mapped[int] = mapped_column(Integer, default=800)
    max_total_context_chars: Mapped[int] = mapped_column(Integer, default=2500)
    max_semantic_expansions: Mapped[int] = mapped_column(Integer, default=5)
    context_builder_mode: Mapped[str] = mapped_column(String(32), default="full_content")
    max_context_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    chunk_merge_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ranking_freshness_weight: Mapped[float] = mapped_column(Float, default=0.05)
    enable_chat_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    llm_retry_max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    llm_retry_on_timeout_only: Mapped[bool] = mapped_column(Boolean, default=True)
    prefer_user_language_sources: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_source_intelligence: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_llm_source_intelligence: Mapped[bool] = mapped_column(Boolean, default=True)
    source_intelligence_importance_threshold: Mapped[int] = mapped_column(Integer, default=70)
    penalize_campaigns_for_overview: Mapped[bool] = mapped_column(Boolean, default=True)
    source_intelligence_db_batch_size: Mapped[int] = mapped_column(Integer, default=50)
    source_intelligence_page_size: Mapped[int] = mapped_column(Integer, default=100)
    source_intelligence_worker_count: Mapped[int] = mapped_column(Integer, default=0)
    source_intelligence_progress_flush_every_sources: Mapped[int] = mapped_column(Integer, default=10)
    source_intelligence_progress_flush_interval_seconds: Mapped[int] = mapped_column(Integer, default=3)
    source_intelligence_cache_invalidation_mode: Mapped[str] = mapped_column(
        String(32), default="version_bump_only"
    )
    run_source_intelligence_inline_during_indexing: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    knowledge_profile_json: Mapped[str] = mapped_column(Text, default="")

    # --- Document-first retrieval engine ---
    retrieval_profile: Mapped[str] = mapped_column(String(32), default="automatic")
    document_priorities_json: Mapped[str] = mapped_column(Text, default="")
    intent_profiles_json: Mapped[str] = mapped_column(Text, default="")
    scoring_weights_json: Mapped[str] = mapped_column(Text, default="")
    top_k_dense: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_k_lexical: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rerank_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Tracing, observability, production limits ---
    enable_tracing: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_trace_storage: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_request_metadata_logging: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_chat_debug_payload: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_semantic_diagnostics_v2: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_namespace_v2_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_shadow_write_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_evidence_assist_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_trace_retention_days: Mapped[int] = mapped_column(Integer, default=30)

    max_concurrent_chat_requests: Mapped[int] = mapped_column(Integer, default=20)
    max_concurrent_llm_requests: Mapped[int] = mapped_column(Integer, default=2)
    max_concurrent_embedding_requests: Mapped[int] = mapped_column(Integer, default=2)
    max_concurrent_background_embedding_requests: Mapped[int] = mapped_column(
        Integer, default=1
    )

    chat_total_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    ollama_generation_timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    ollama_embedding_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    qdrant_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
