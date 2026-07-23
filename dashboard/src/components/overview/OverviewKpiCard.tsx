import type { ReactNode } from "react";
import { MetricCard, StatusBadge, healthStatusToBadge, type MetricTone } from "../../ui";

export type KpiTone = "green" | "teal" | "purple" | "blue" | "orange" | "pink" | "neutral";

interface Props {
  label: string;
  icon: ReactNode;
  tone?: KpiTone;
  value?: ReactNode;
  status?: string;
  statusLabel?: string;
  compactValue?: boolean;
}

const TONE_MAP: Record<KpiTone, MetricTone> = {
  green: "success",
  teal: "info",
  purple: "primary",
  blue: "info",
  orange: "warning",
  pink: "danger",
  neutral: "neutral",
};

export default function OverviewKpiCard({
  label,
  icon,
  tone = "purple",
  value,
  status,
  statusLabel,
  compactValue = false,
}: Props) {
  const displayValue =
    status != null && statusLabel != null ? (
      <StatusBadge variant={healthStatusToBadge(status)} label={statusLabel} />
    ) : (
      value
    );

  return (
    <MetricCard
      label={label}
      icon={icon}
      tone={TONE_MAP[tone]}
      value={
        compactValue ? (
          <span style={{ fontSize: 18, fontWeight: 600 }}>{displayValue}</span>
        ) : (
          displayValue
        )
      }
      hover
    />
  );
}
