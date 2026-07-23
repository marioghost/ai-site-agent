import type { ReactNode } from "react";
import { cn } from "../utils/cn";

type Props = {
  label?: string;
  percent?: number | null;
  indeterminate?: boolean;
  className?: string;
};

export function ProgressBar({ label, percent, indeterminate = false, className }: Props) {
  return (
    <div className={cn("ds-progress", className)}>
      {label && <div className="ds-progress__label">{label}</div>}
      <div className={cn("ds-progress__track", indeterminate && "ds-progress__track--indeterminate")}>
        {!indeterminate && percent != null && (
          <div className="ds-progress__fill" style={{ width: `${Math.min(100, percent)}%` }} />
        )}
      </div>
    </div>
  );
}

type ProgressCardProps = {
  title: string;
  value?: ReactNode;
  percent?: number;
  description?: string;
  className?: string;
};

export function ProgressCard({ title, value, percent, description, className }: ProgressCardProps) {
  return (
    <article className={cn("ds-progress-card", className)}>
      <div className="ds-progress-card__header">
        <h3 className="ds-progress-card__title">{title}</h3>
        {value != null && <span className="ds-progress-card__value">{value}</span>}
      </div>
      {description && <p className="ds-progress-card__description">{description}</p>}
      {percent != null && <ProgressBar percent={percent} />}
    </article>
  );
}

type RingProps = { percent: number; size?: number; label?: string };

export function ProgressRing({ percent, size = 48, label }: RingProps) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.min(100, percent) / 100) * c;

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--ds-border)" strokeWidth={4} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--ds-color-primary)"
          strokeWidth={4}
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      {label && <span className="ds-caption">{label}</span>}
    </div>
  );
}
