import { Link } from "react-router-dom";
import type { AnalyticsSummary, TimeseriesPoint } from "../../types";
import MetricCard from "./MetricCard";
import OverviewGrid from "./OverviewGrid";
import { IconChart } from "./icons";

interface Props {
  title: string;
  viewAllLabel: string;
  requestsLabel: string;
  avgLatencyLabel: string;
  cacheHitLabel: string;
  errorCountLabel: string;
  chartLabel: string;
  noDataLabel: string;
  hoursLabel: string;
  summary: AnalyticsSummary | null;
  timeseries: TimeseriesPoint[];
  formatMs: (n: number) => string;
  formatPct: (n: number) => string;
}

function MiniBarChart({
  points,
  valueKey,
  label,
}: {
  points: TimeseriesPoint[];
  valueKey: "requests" | "avg_latency_ms" | "cache_hit_rate";
  label: string;
}) {
  const max = Math.max(...points.map((p) => p[valueKey]), 1);

  return (
    <div className="overview-mini-chart">
      <div className="overview-mini-chart__label">{label}</div>
      <div className="overview-mini-chart__bars" role="img" aria-label={label}>
        {points.map((p) => {
          const v = p[valueKey];
          const h = Math.max(6, (v / max) * 100);
          return (
            <div
              key={p.hour}
              className="overview-mini-chart__bar"
              style={{ height: `${h}%` }}
              title={`${new Date(p.hour).toLocaleString()}: ${v}`}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function AnalyticsPreviewSection({
  title,
  viewAllLabel,
  requestsLabel,
  avgLatencyLabel,
  cacheHitLabel,
  errorCountLabel,
  chartLabel,
  noDataLabel,
  hoursLabel,
  summary,
  timeseries,
  formatMs,
  formatPct,
}: Props) {
  if (!summary) return null;

  return (
    <section className="overview-section">
      <div className="overview-section__head">
        <h2 className="overview-section__title">{title}</h2>
        <Link to="/analytics" className="overview-link-btn">
          {viewAllLabel}
        </Link>
      </div>
      <OverviewGrid variant="analytics">
        <MetricCard
          label={requestsLabel}
          value={summary.requests_today}
          icon={<IconChart size={18} />}
          compact
        />
        <MetricCard
          label={avgLatencyLabel}
          value={formatMs(summary.average_latency_ms)}
          compact
        />
        <MetricCard
          label={cacheHitLabel}
          value={formatPct(summary.cache_hit_rate)}
          compact
        />
        <MetricCard label={errorCountLabel} value={summary.error_count} compact />
      </OverviewGrid>
      <article className="overview-panel overview-panel--chart">
        {timeseries.length === 0 ? (
          <p className="overview-panel__empty">{noDataLabel}</p>
        ) : (
          <>
            <MiniBarChart points={timeseries} valueKey="requests" label={chartLabel} />
            <p className="overview-panel__meta">{hoursLabel}</p>
          </>
        )}
      </article>
    </section>
  );
}
