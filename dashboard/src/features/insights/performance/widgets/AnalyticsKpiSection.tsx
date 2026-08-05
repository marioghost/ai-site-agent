import { useMemo } from "react";
import {
  MessageSquare,
  MessagesSquare,
  Users,
  CheckCircle2,
  Brain,
  Database,
  AlertTriangle,
  Clock,
} from "lucide-react";
import type { MetricTrend, ProductAnalyticsSummary } from "../../../../types";
import { MetricGrid } from "../../../../ui";
import AnalyticsKpiCard from "./AnalyticsKpiCard";
import { useTranslation } from "../../../../i18n";

function formatTrend(trend: MetricTrend | undefined): {
  label?: string;
  direction: "up" | "down" | "neutral";
} {
  if (!trend || trend.change_pct == null) return { direction: "neutral" };
  const sign = trend.change_pct > 0 ? "+" : "";
  return {
    label: `${sign}${trend.change_pct}%`,
    direction: trend.direction as "up" | "down" | "neutral",
  };
}

type Props = {
  summary: ProductAnalyticsSummary;
  pct: (n: number) => string;
  msLabel: (n: number) => string;
};

export default function AnalyticsKpiSection({ summary, pct, msLabel }: Props) {
  const { t } = useTranslation();

  const items = useMemo(
    () => [
      {
        key: "conversations",
        label: t("analytics.kpi.conversations"),
        value: summary.total_conversations,
        icon: <MessageSquare size={18} />,
        tone: "primary" as const,
        trend: formatTrend(summary.trends.total_requests),
      },
      {
        key: "messages",
        label: t("analytics.kpi.messages"),
        value: summary.total_messages,
        icon: <MessagesSquare size={18} />,
        tone: "info" as const,
      },
      {
        key: "users",
        label: t("analytics.kpi.unique_users"),
        value: summary.unique_users,
        icon: <Users size={18} />,
        tone: "info" as const,
      },
      {
        key: "success",
        label: t("analytics.kpi.successful"),
        value: summary.successful_responses,
        icon: <CheckCircle2 size={18} />,
        tone: "success" as const,
        trend: formatTrend(summary.trends.successful_responses),
      },
      {
        key: "context",
        label: t("analytics.kpi.context_usage"),
        value: pct(summary.context_usage_rate),
        icon: <Brain size={18} />,
        tone: "primary" as const,
        trend: formatTrend(summary.trends.context_usage_rate),
        compact: true,
      },
      {
        key: "cache",
        label: t("analytics.kpi.cache_hit"),
        value: pct(summary.cache_hit_rate),
        icon: <Database size={18} />,
        tone: "success" as const,
        trend: formatTrend(summary.trends.cache_hit_rate),
        compact: true,
      },
      {
        key: "fallback",
        label: t("analytics.kpi.fallback"),
        value: pct(summary.fallback_rate),
        icon: <AlertTriangle size={18} />,
        tone: "warning" as const,
        trend: formatTrend(summary.trends.fallback_rate),
        compact: true,
      },
      {
        key: "latency",
        label: t("analytics.kpi.avg_latency"),
        value: msLabel(summary.average_latency_ms),
        icon: <Clock size={18} />,
        tone: "neutral" as const,
        trend: formatTrend(summary.trends.average_latency_ms),
        compact: true,
      },
    ],
    [summary, t, pct, msLabel]
  );

  return (
    <MetricGrid columns={4}>
      {items.map((item) => (
        <AnalyticsKpiCard
          key={item.key}
          label={item.label}
          value={item.value}
          icon={item.icon}
          tone={item.tone}
          trend={item.trend?.label}
          trendDirection={item.trend?.direction}
          compact={item.compact}
        />
      ))}
    </MetricGrid>
  );
}
