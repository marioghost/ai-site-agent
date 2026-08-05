import type { RetrievalQualityMetrics } from "../../../../types";
import { MetricCard, MetricGrid, SectionCard } from "../../../../ui";
import { useTranslation } from "../../../../i18n";

type Props = {
  metrics: RetrievalQualityMetrics;
  pct: (n: number) => string;
  msLabel: (n: number) => string;
};

export default function RetrievalQualitySection({ metrics, pct, msLabel }: Props) {
  const { t } = useTranslation();

  return (
    <SectionCard title={t("analytics.retrieval_quality")} subtitle={t("analytics.retrieval_quality_hint")}>
      <MetricGrid columns={4}>
        <MetricCard
          label={t("analytics.retrieval.avg_score")}
          value={metrics.avg_retrieval_score.toFixed(3)}
          tone="primary"
        />
        <MetricCard
          label={t("analytics.retrieval.avg_chunks")}
          value={metrics.avg_chunk_count.toFixed(1)}
          tone="info"
        />
        <MetricCard
          label={t("analytics.retrieval.context_chars")}
          value={Math.round(metrics.avg_context_chars).toLocaleString()}
          tone="neutral"
        />
        <MetricCard
          label={t("analytics.retrieval.context_usage")}
          value={pct(metrics.context_usage_rate)}
          tone="success"
        />
        <MetricCard
          label={t("analytics.retrieval.without_context")}
          value={metrics.responses_without_context}
          tone="warning"
        />
        <MetricCard
          label={t("analytics.retrieval.search_ms")}
          value={msLabel(metrics.avg_retrieval_ms)}
          tone="info"
        />
        <MetricCard
          label={t("analytics.retrieval.llm_ms")}
          value={msLabel(metrics.avg_generation_ms)}
          tone="primary"
        />
        <MetricCard
          label={t("analytics.retrieval.prompt_chars")}
          value={Math.round(metrics.avg_prompt_chars).toLocaleString()}
          tone="neutral"
        />
      </MetricGrid>
    </SectionCard>
  );
}
