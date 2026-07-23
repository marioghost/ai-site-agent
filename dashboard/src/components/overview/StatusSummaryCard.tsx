import type { ReactNode } from "react";
import StatusIndicator from "./StatusIndicator";

interface Props {
  label: string;
  status: string;
  statusLabel: string;
  icon: ReactNode;
}

export default function StatusSummaryCard({ label, status, statusLabel, icon }: Props) {
  return (
    <article className="overview-card overview-card--status">
      <div className="overview-card__icon-wrap">{icon}</div>
      <div className="overview-card__body">
        <span className="overview-card__label">{label}</span>
        <StatusIndicator status={status} label={statusLabel} />
      </div>
    </article>
  );
}
