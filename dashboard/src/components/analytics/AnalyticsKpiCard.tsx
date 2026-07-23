import type { ReactNode } from "react";
import { MetricCard, type MetricTone } from "../../ui";

type Props = {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: MetricTone;
  trend?: string;
  trendDirection?: "up" | "down" | "neutral";
  compact?: boolean;
};

export default function AnalyticsKpiCard({
  label,
  value,
  icon,
  tone = "primary",
  trend,
  trendDirection = "neutral",
  compact = false,
}: Props) {
  return (
    <MetricCard
      label={label}
      value={compact ? <span className="ds-analytics-kpi__value">{value}</span> : value}
      icon={icon}
      tone={tone}
      delta={trend}
      deltaDirection={trendDirection === "down" ? "down" : "up"}
    />
  );
}
