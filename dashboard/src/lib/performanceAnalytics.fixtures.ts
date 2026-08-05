import type { RetrievalQualityMetrics, SourceAnalyticsPayload } from "../types";

export const ZERO_RETRIEVAL: RetrievalQualityMetrics = {
  avg_retrieval_score: 0,
  avg_rerank_score: 0,
  avg_chunk_count: 0,
  avg_context_chars: 0,
  avg_prompt_chars: 0,
  context_usage_rate: 0,
  responses_without_context: 0,
  avg_retrieval_ms: 0,
  avg_generation_ms: 0,
};

export const EMPTY_SOURCES: SourceAnalyticsPayload = { top_pages: [], unused_sources: [] };
