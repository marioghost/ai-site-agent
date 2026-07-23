"""Pydantic schemas for chat and chat logs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ChatSource
from app.schemas.semantic_diagnostics import UnderstandingTraceRead
from app.schemas.trace import RequestMetadataRead, TimingMetrics, TracePayload


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    debug: bool = False
    bypass_cache: bool = False
    skip_user_message: bool = False


class CacheStatusRead(BaseModel):
    answer_cache_hit: bool = False
    retrieval_cache_hit: bool = False
    cache_type: str = "none"
    cache_age_seconds: int | None = None
    cache_key: str | None = None
    cache_namespace: dict[str, str] | None = None
    cache_ttl_seconds: int | None = None
    cached_selected_chunk_count: int = 0
    cached_context_used: bool = False
    negative_cache: bool = False
    bypassed: bool = False
    invalidation_version: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    request_id: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)
    used_context: bool = False
    cache_hit: bool = False
    cache_type: str = "none"  # none | retrieval_success | answer_success | ...
    error_type: str | None = None
    prompt_diagnostics: dict | None = None
    cache: CacheStatusRead | None = None
    timing: TimingMetrics = Field(default_factory=TimingMetrics)
    trace: TracePayload | None = None
    metadata: RequestMetadataRead | None = None
    retrieval_debug: dict | None = None
    understanding_trace: UnderstandingTraceRead | None = None


class CacheClearResponse(BaseModel):
    cleared_retrieval_rows: int = 0
    cleared_answer_cache: bool = False
    reason: str = ""


class ChatLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str | None = None
    request_id: str | None = None
    user_message: str
    assistant_answer: str
    used_context: bool
    sources: list[ChatSource] = Field(default_factory=list)
    cache_hit: bool = False
    cache_type: str = "none"
    retrieval_ms: int = 0
    generation_ms: int = 0
    polish_ms: int = 0
    created_at: datetime | None = None


class ChatLogListResponse(BaseModel):
    items: list[ChatLogRead]
    total: int
    page: int
    page_size: int
