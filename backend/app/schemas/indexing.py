"""Pydantic schemas for indexing jobs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IndexStartRequest(BaseModel):
    """Optional overrides; if omitted the saved settings are used."""

    site_url: str | None = None
    sitemap_url: str | None = None
    crawl_depth: int | None = None
    allowed_domains: list[str] | None = None
    deny_url_patterns: list[str] | None = None
    max_pages_per_run: int | None = None
    max_files_per_run: int | None = None
    scan_mode: str | None = None
    enable_file_indexing: bool | None = None
    scan_all_pages: bool | None = None
    scan_all_files: bool | None = None
    force_reindex: bool | None = None
    pending_only: bool | None = None


class IndexLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class IndexActivityEntry(BaseModel):
    time: str
    level: str = "info"
    message: str


class IndexRunProgress(BaseModel):
    selected_total: int = 0
    processed_total: int = 0
    selected_pages: int = 0
    selected_files: int = 0
    processed_pages: int = 0
    processed_files: int = 0
    percent: float | None = None
    is_indeterminate: bool = True


class IndexRunSummary(BaseModel):
    found_pages: int = 0
    found_files: int = 0
    selected_pages: int = 0
    selected_files: int = 0
    processed_pages: int = 0
    processed_files: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0


class IndexDiscoveryStatus(BaseModel):
    discovered_urls: int = 0
    discovered_pages: int = 0
    discovered_files: int = 0
    already_known_urls: int = 0
    newly_discovered_urls: int = 0


class IndexQueueStatus(BaseModel):
    new_pages_waiting: int = 0
    failed_pages_waiting: int = 0
    stale_pages_waiting: int = 0
    fresh_pages_skipped_until_refresh: int = 0
    queued_pages_for_this_run: int = 0
    total_pages_waiting: int = 0


class IndexPagesStatus(BaseModel):
    processed_pages: int = 0
    indexed_new_pages: int = 0
    updated_pages: int = 0
    unchanged_pages: int = 0
    skipped_empty_pages: int = 0
    skipped_fresh_pages: int = 0
    failed_pages: int = 0


class IndexFilesStatus(BaseModel):
    discovered_files: int = 0
    queued_files_for_this_run: int = 0
    processed_files: int = 0
    indexed_new_files: int = 0
    updated_files: int = 0
    unchanged_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0


class IndexAdvancedStatus(BaseModel):
    current_phase: str | None = None
    discovery: IndexDiscoveryStatus = Field(default_factory=IndexDiscoveryStatus)
    queue: IndexQueueStatus = Field(default_factory=IndexQueueStatus)
    pages: IndexPagesStatus = Field(default_factory=IndexPagesStatus)
    files: IndexFilesStatus = Field(default_factory=IndexFilesStatus)
    errors_count: int = 0
    log: list[IndexLogEntry] = Field(default_factory=list)


class IndexJobStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    status: str = "idle"
    current_phase: str | None = None
    stage: str = "idle"
    run_mode: str | None = None
    current_url: str | None = None
    current_url_type: str | None = None
    current_action: str | None = None
    last_activity_at: str | None = None
    last_activity_message: str | None = None
    heartbeat_counter: int = 0
    alive_state: str = "unknown"
    seconds_since_activity: int | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None

    progress: IndexRunProgress = Field(default_factory=IndexRunProgress)
    summary: IndexRunSummary = Field(default_factory=IndexRunSummary)
    recent_activity: list[IndexActivityEntry] = Field(default_factory=list)
    advanced: IndexAdvancedStatus | None = None

    discovery: IndexDiscoveryStatus = Field(default_factory=IndexDiscoveryStatus)
    queue: IndexQueueStatus = Field(default_factory=IndexQueueStatus)
    pages: IndexPagesStatus = Field(default_factory=IndexPagesStatus)
    files: IndexFilesStatus = Field(default_factory=IndexFilesStatus)

    log_tail: list[IndexLogEntry] = Field(default_factory=list)
    log: list[IndexLogEntry] = Field(default_factory=list)

    # Legacy flat fields (deprecated; mirrored from nested counters)
    discovered_pages: int = 0
    new_pages: int = 0
    queued_pages: int = 0
    processed_pages: int = 0
    indexed_pages: int = 0
    unchanged_pages: int = 0
    skipped_pages: int = 0
    skipped_fresh_pages: int = 0
    failed_pages: int = 0
    stale_pages: int = 0
    discovered_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    errors_count: int = 0
    intelligence_sample_profiles: list[dict] = Field(default_factory=list)
    intelligence_selected_sources: int = 0
    intelligence_updated_sources: int = 0
    dry_run: bool = False
    skipped_unchanged: int = 0
    would_skip_unchanged: int = 0
    would_call_llm: int = 0
    llm_cache_hits: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    avg_ms_per_source: float = 0.0
    estimated_time_with_llm: float = 0.0
    estimated_remaining_seconds: int | None = None
    worker_count: int = 0
    batch_size: int = 0


class IndexQueuePreview(BaseModel):
    queue: IndexQueueStatus = Field(default_factory=IndexQueueStatus)
    max_pages_per_run: int = 0
    estimated_runs_remaining: int = 0

    # Legacy flat fields
    new_pages: int = 0
    failed_pages: int = 0
    skipped_pages_waiting: int = 0
    stale_pages: int = 0
    fresh_pages: int = 0
    queued_pages: int = 0
    total_sources: int = 0


class ReprocessExistingRequest(BaseModel):
    scope: str = "all"
    source_ids: list[int] = Field(default_factory=list)
    status: list[str] = Field(default_factory=lambda: ["indexed"])
    rebuild_chunks: bool = True
    rebuild_embeddings: bool = True
    reclassify_document_types: bool = True
    recalculate_content_hints: bool = True
    remove_boilerplate: bool = True
    invalidate_caches: bool = True
    limit: int | None = None
    dry_run: bool = False
    needs_reprocess_only: bool = False


class ReprocessExistingResponse(BaseModel):
    job_id: str
    status: str
    selected_sources: int = 0
    estimated_chunks: int = 0
    sample_boilerplate_ratios: list[float] = Field(default_factory=list)


class GenerateSourceIntelligenceRequest(BaseModel):
    scope: str = "needs_intelligence"
    source_ids: list[int] = Field(default_factory=list)
    limit: int | None = None
    dry_run: bool = False
    generate_summaries: bool = False


class GenerateSourceIntelligenceResponse(BaseModel):
    job_id: str = ""
    status: str
    selected_sources: int = 0
    updated_sources: int = 0
    sample_profiles: list[dict] = Field(default_factory=list)
