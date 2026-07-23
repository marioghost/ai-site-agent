import type { AnalyticsSummary, IntentDistributionRow, TimeseriesPoint } from "../../types";
import { topIntentRows } from "../../lib/intentDistribution";
import DistributionBarChart from "../analytics/DistributionBarChart";
import RequestsLineChartCard from "./RequestsLineChartCard";
import SystemStatsCard, { type StatItem } from "./SystemStatsCard";
import {
  IconChart,
  IconFile,
  IconFolder,
  IconSync,
} from "./icons";

type Props = {
  statsTitle: string;
  lineChartTitle: string;
  intentsTitle: string;
  intentsHint: string;
  emptyLabel: string;
  sourceCount: number;
  readyToUse?: number;
  summary: AnalyticsSummary | null;
  timeseries: TimeseriesPoint[];
  intents: IntentDistributionRow[];
  statLabels: {
    sources: string;
    requests: string;
    latency: string;
    accuracy: string;
    cache: string;
    errors: string;
  };
  deltaLabels: {
    today: string;
    perDay: string;
  };
  formatLatency: (ms: number) => string;
  formatPct: (n: number) => string;
  labelIntent: (intent: string) => string;
};

export default function AnalyticsPreviewRow({
  statsTitle,
  lineChartTitle,
  intentsTitle,
  intentsHint,
  emptyLabel,
  sourceCount,
  readyToUse,
  summary,
  timeseries,
  intents,
  statLabels,
  deltaLabels,
  formatLatency,
  formatPct,
  labelIntent,
}: Props) {
  if (!summary) return null;

  const statItems: StatItem[] = [
    {
      id: "sources",
      label: statLabels.sources,
      value: readyToUse ?? sourceCount,
      delta: `+0 ${deltaLabels.perDay}`,
      deltaTone: "neutral",
      icon: <IconFolder size={16} />,
      iconTone: "blue",
    },
    {
      id: "requests",
      label: statLabels.requests,
      value: summary.total_requests,
      delta: `+${summary.requests_today} ${deltaLabels.today}`,
      deltaTone: "up",
      icon: <IconChart size={16} />,
      iconTone: "purple",
    },
    {
      id: "latency",
      label: statLabels.latency,
      value: formatLatency(summary.average_latency_ms),
      delta: undefined,
      icon: <IconSync size={16} />,
      iconTone: "teal",
    },
    {
      id: "accuracy",
      label: statLabels.accuracy,
      value: formatPct(summary.context_usage_rate),
      delta: undefined,
      icon: <IconFile size={16} />,
      iconTone: "green",
    },
    {
      id: "cache",
      label: statLabels.cache,
      value: formatPct(summary.cache_hit_rate),
      delta: undefined,
      icon: <IconChart size={16} />,
      iconTone: "orange",
    },
    {
      id: "errors",
      label: statLabels.errors,
      value: summary.error_count,
      delta: summary.error_count > 0 ? `-${summary.error_count}` : undefined,
      deltaTone: "down",
      icon: <IconSync size={16} />,
      iconTone: "red",
    },
  ];

  const intentRows = topIntentRows(intents, labelIntent, 5);

  return (
    <section className="ov-analytics-row">
      <SystemStatsCard title={statsTitle} items={statItems} />
      <RequestsLineChartCard title={lineChartTitle} points={timeseries} emptyLabel={emptyLabel} />
      <DistributionBarChart
        className="ov-analytics-card ov-analytics-card--distribution"
        title={intentsTitle}
        subtitle={intentsHint}
        rows={intentRows}
        emptyLabel={emptyLabel}
        labelKey={(row) => row.label}
      />
    </section>
  );
}
