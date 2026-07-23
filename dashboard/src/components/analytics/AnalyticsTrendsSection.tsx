import type { TimeseriesPoint } from "../../types";
import TrendChartCard from "./TrendChartCard";
import { useTranslation } from "../../i18n";

type Props = {
  timeseries: TimeseriesPoint[];
  msLabel: (n: number) => string;
  pct: (n: number) => string;
};

export default function AnalyticsTrendsSection({ timeseries, msLabel, pct }: Props) {
  const { t } = useTranslation();

  return (
    <section className="an-charts-section">
      <TrendChartCard
        title={t("analytics.chart.requests_hour")}
        points={timeseries}
        valueKey="requests"
        emptyLabel={t("common.no_data_period")}
        variant="purple"
        tall
      />
      <div className="an-charts-stack">
        <TrendChartCard
          title={t("analytics.chart.avg_latency")}
          points={timeseries}
          valueKey="avg_latency_ms"
          emptyLabel={t("common.no_data_period")}
          variant="teal"
          formatValue={(v) => msLabel(v)}
        />
        <TrendChartCard
          title={t("analytics.chart.cache_hit")}
          points={timeseries}
          valueKey="cache_hit_rate"
          emptyLabel={t("common.no_data_period")}
          variant="orange"
          formatValue={(v) => pct(v)}
        />
        <TrendChartCard
          title={t("analytics.chart.fallback_rate")}
          points={timeseries}
          valueKey="fallback_rate"
          emptyLabel={t("common.no_data_period")}
          variant="purple"
          formatValue={(v) => pct(v)}
        />
      </div>
    </section>
  );
}
