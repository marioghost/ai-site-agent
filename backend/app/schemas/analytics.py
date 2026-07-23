"""Analytics API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MetricTrend(BaseModel):
    value: float = 0.0
    previous_value: float = 0.0
    change_pct: float | None = None
    direction: str = "neutral"


class AnalyticsSummary(BaseModel):
    total_requests: int = 0
    requests_today: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    fallback_rate: float = 0.0
    context_usage_rate: float = 0.0
    error_count: int = 0


class ProductAnalyticsSummary(BaseModel):
    total_conversations: int = 0
    total_messages: int = 0
    unique_users: int = 0
    total_requests: int = 0
    successful_responses: int = 0
    success_rate: float = 0.0
    context_usage_rate: float = 0.0
    cache_hit_rate: float = 0.0
    fallback_rate: float = 0.0
    average_latency_ms: float = 0.0
    trends: dict[str, MetricTrend] = Field(default_factory=dict)


class TimeseriesPoint(BaseModel):
    hour: str
    requests: int = 0
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    fallback_rate: float = 0.0
    context_usage_rate: float = 0.0


class UnansweredQuery(BaseModel):
    query: str
    count: int


class SlowQuery(BaseModel):
    request_id: str
    query: str
    total_ms: int
    cache_hit: bool
    created_at: str | None = None


class PopularQueryRow(BaseModel):
    query: str
    count: int = 0
    avg_response_ms: float = 0.0
    cache_hit_rate: float = 0.0
    fallback_count: int = 0
    success_rate: float = 0.0


class ProblematicQueryRow(BaseModel):
    query: str
    occurrences: int = 0
    fallback_count: int = 0
    timeout_count: int = 0
    retrieval_failure_count: int = 0
    avg_retrieval_score: float = 0.0


class RetrievalQualityMetrics(BaseModel):
    avg_retrieval_score: float = 0.0
    avg_rerank_score: float = 0.0
    avg_chunk_count: float = 0.0
    avg_context_chars: float = 0.0
    avg_prompt_chars: float = 0.0
    context_usage_rate: float = 0.0
    responses_without_context: int = 0
    avg_retrieval_ms: float = 0.0
    avg_generation_ms: float = 0.0


class SourceUsageRow(BaseModel):
    title: str
    url: str
    usage_count: int = 0
    avg_score: float = 0.0
    last_used_at: str | None = None


class UnusedSourceRow(BaseModel):
    title: str
    url: str
    indexed_at: str | None = None
    document_type: str = "generic_page"


class IntentDistributionRow(BaseModel):
    intent: str
    count: int = 0
    share: float = 0.0


class TopicDistributionRow(BaseModel):
    topic_key: str
    topic_label: str
    count: int = 0
    share: float = 0.0


class AnalyticsInsight(BaseModel):
    id: str
    severity: str = "info"
    message_key: str
    params: dict[str, str | int | float] = Field(default_factory=dict)


class AnalyticsRecommendation(BaseModel):
    id: str
    stars: int = 3
    message_key: str
    params: dict[str, str | int | float] = Field(default_factory=dict)


class SourceAnalyticsPayload(BaseModel):
    top_pages: list[SourceUsageRow] = Field(default_factory=list)
    unused_sources: list[UnusedSourceRow] = Field(default_factory=list)


class PerformanceStatus(BaseModel):
    active_requests: int = 0
    queued_requests: int = 0
    max_concurrent_llm_requests: int = 2
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    ollama_status: str = "unknown"
    qdrant_status: str = "unknown"
