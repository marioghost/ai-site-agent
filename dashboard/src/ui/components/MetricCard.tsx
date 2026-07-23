import type { CSSProperties, ReactNode } from "react";
import { cn } from "../utils/cn";

export type MetricTone = "primary" | "success" | "warning" | "danger" | "info" | "neutral";

type StatCardProps = {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  tone?: MetricTone;
  trend?: string;
  trendDirection?: "up" | "down";
  badge?: ReactNode;
  interactive?: boolean;
  className?: string;
  footer?: ReactNode;
};

/** Single reusable KPI / stat card primitive. */
export function StatCard({
  label,
  value,
  icon,
  tone = "primary",
  trend,
  trendDirection = "up",
  badge,
  interactive = true,
  className,
  footer,
}: StatCardProps) {
  return (
    <article
      className={cn(
        "ds-stat-card",
        interactive && "ds-stat-card--interactive",
        className
      )}
    >
      {(icon || badge) && (
        <div className="ds-stat-card__top">
          {icon && (
            <div className={cn("ds-stat-card__icon", `ds-metric-card__icon--${tone}`)}>
              <span className="ds-icon ds-icon--sm">{icon}</span>
            </div>
          )}
          {badge}
        </div>
      )}
      <div className="ds-stat-card__label">{label}</div>
      <div className="ds-stat-card__value">{value}</div>
      {trend && (
        <div className={cn("ds-stat-card__trend", `ds-stat-card__trend--${trendDirection}`)}>
          {trend}
        </div>
      )}
      {footer}
    </article>
  );
}

type MetricCardProps = Omit<StatCardProps, "trend" | "trendDirection" | "footer"> & {
  helper?: string;
  delta?: string;
  deltaDirection?: "up" | "down";
  hover?: boolean;
  children?: ReactNode;
};

/** MetricCard — alias over StatCard with delta/helper support. */
export function MetricCard({
  label,
  value,
  icon,
  tone = "primary",
  helper,
  delta,
  deltaDirection = "up",
  badge,
  hover = true,
  children,
  className,
}: MetricCardProps) {
  const footer = (
    <>
      {helper && <div className="ds-metric-card__helper">{helper}</div>}
      {children}
    </>
  );
  return (
    <StatCard
      label={label}
      value={value}
      icon={icon}
      tone={tone}
      trend={delta}
      trendDirection={deltaDirection}
      badge={badge}
      interactive={hover}
      className={className}
      footer={helper || children ? footer : undefined}
    />
  );
}

type GridProps = {
  columns?: 3 | 4 | 6 | "auto";
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
};

export function MetricGrid({ columns = "auto", children, className, style }: GridProps) {
  return (
    <div
      className={cn(
        "ds-metric-grid",
        columns === 6 && "ds-metric-grid--6",
        columns === 4 && "ds-metric-grid--4",
        columns === 3 && "ds-metric-grid--3",
        className
      )}
      style={style}
    >
      {children}
    </div>
  );
}
