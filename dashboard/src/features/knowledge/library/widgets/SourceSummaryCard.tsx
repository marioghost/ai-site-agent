import type { ReactNode } from "react";
import { MetricCard, type MetricTone } from "../../../../ui";

type KpiTone = "green" | "teal" | "purple" | "blue" | "orange" | "pink" | "neutral";

type Props = {
  label: string;
  helper: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: KpiTone;
};

const TONE_MAP: Record<KpiTone, MetricTone> = {
  green: "success",
  teal: "info",
  purple: "primary",
  blue: "info",
  orange: "warning",
  pink: "danger",
  neutral: "neutral",
};

export default function SourceSummaryCard({
  label,
  helper,
  value,
  icon,
  tone = "purple",
}: Props) {
  return (
    <MetricCard
      label={label}
      value={value}
      icon={icon}
      tone={TONE_MAP[tone]}
      helper={helper}
    />
  );
}
