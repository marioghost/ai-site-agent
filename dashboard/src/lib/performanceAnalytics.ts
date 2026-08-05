import type {
  AnalyticsInsightsPayload,
  IntentDistributionRow,
  RetrievalQualityMetrics,
  SourceAnalyticsPayload,
  TimeseriesPoint,
  TopicDistributionRow,
} from "../types";

/** Zero-filled retrieval payloads are not meaningful analytics. */
export function hasMeaningfulRetrieval(metrics: RetrievalQualityMetrics | null | undefined): boolean {
  if (!metrics) return false;
  return (
    metrics.responses_without_context > 0 ||
    metrics.avg_chunk_count > 0 ||
    metrics.avg_retrieval_score > 0 ||
    metrics.avg_rerank_score > 0 ||
    metrics.avg_context_chars > 0 ||
    metrics.avg_prompt_chars > 0 ||
    metrics.context_usage_rate > 0 ||
    metrics.avg_retrieval_ms > 0 ||
    metrics.avg_generation_ms > 0
  );
}

export function hasMeaningfulSources(data: SourceAnalyticsPayload | null | undefined): boolean {
  if (!data) return false;
  return data.top_pages.length > 0 || data.unused_sources.length > 0;
}

export type PerformancePresence = {
  hasTrend: boolean;
  hasQuery: boolean;
  hasRetrieval: boolean;
  hasSources: boolean;
  hasDistribution: boolean;
  hasInsights: boolean;
  /** True when the page should show the coherent no-data empty state. */
  isEmpty: boolean;
};

/** One pass over Performance datasets for empty gating and section visibility. */
export function evaluatePerformancePresence(input: {
  timeseries: TimeseriesPoint[];
  popularCount: number;
  problematicCount: number;
  retrieval: RetrievalQualityMetrics | null;
  sources: SourceAnalyticsPayload | null;
  intents: IntentDistributionRow[];
  topics: TopicDistributionRow[];
  insights: AnalyticsInsightsPayload | null;
}): PerformancePresence {
  const hasTrend = input.timeseries.some((point) => (point.requests ?? 0) > 0);
  const hasQuery = input.popularCount > 0 || input.problematicCount > 0;
  const hasRetrieval = hasMeaningfulRetrieval(input.retrieval);
  const hasSources = hasMeaningfulSources(input.sources);
  const hasDistribution = input.intents.length > 0 || input.topics.length > 0;
  const hasInsights =
    !!input.insights &&
    (input.insights.insights.length > 0 || input.insights.recommendations.length > 0);
  const isEmpty =
    !hasTrend && !hasQuery && !hasRetrieval && !hasSources && !hasDistribution && !hasInsights;
  return { hasTrend, hasQuery, hasRetrieval, hasSources, hasDistribution, hasInsights, isEmpty };
}
