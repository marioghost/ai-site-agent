"""Pydantic schemas for answer traces."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ChatSource


class TraceStepRead(BaseModel):
    name: str
    status: str
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunkRead(BaseModel):
    title: str
    url: str
    source_type: str
    heading: str = ""
    document_type: str = "generic_page"
    content_type_hint: str = "generic"
    dense_score: float = 0.0
    lexical_score: float = 0.0
    final_score: float = 0.0
    used_in_context: bool = False
    is_canonical: bool = False
    excluded_as_news: bool = False
    text_preview: str = ""


class TracePayload(BaseModel):
    steps: list[TraceStepRead] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkRead] = Field(default_factory=list)


class RequestMetadataRead(BaseModel):
    request_id: str
    session_id: str | None = None
    user_ip: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    knowledge_version: int = 1
    retrieval_mode: str = "hybrid"
    query_intent: str = "unknown"
    applied_knowledge_config: dict | None = None
    created_at: str | None = None


class TimingMetrics(BaseModel):
    total_ms: int = 0
    retrieval_ms: int = 0
    generation_ms: int = 0
    polish_ms: int = 0


class AnswerTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str
    session_id: str | None = None
    user_ip: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    original_query: str
    normalized_query: str
    expanded_queries: list[str] = Field(default_factory=list)
    answer_text: str
    sources: list[ChatSource] = Field(default_factory=list)
    trace: TracePayload = Field(default_factory=TracePayload)
    cache_hit: bool = False
    cache_type: str = "none"
    used_context: bool = False
    retrieval_mode: str = "hybrid"
    knowledge_version: int = 1
    timing: TimingMetrics = Field(default_factory=TimingMetrics)
    created_at: datetime | None = None


class AnswerTraceListResponse(BaseModel):
    items: list[AnswerTraceRead]
    total: int
    page: int
    page_size: int
