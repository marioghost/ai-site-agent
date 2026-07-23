import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  compact?: boolean;
}

export default function MetricCard({ label, value, icon, compact = false }: Props) {
  return (
    <article className={`overview-card overview-card--metric${compact ? " overview-card--compact" : ""}`}>
      {icon && <div className="overview-card__icon-wrap">{icon}</div>}
      <div className="overview-card__body">
        <span className="overview-card__label">{label}</span>
        <div className="overview-card__value">{value}</div>
      </div>
    </article>
  );
}
