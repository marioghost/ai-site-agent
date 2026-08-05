import { cn } from "../../../../ui/utils/cn";

type Row = { label: string; count: number; share: number };

type Props = {
  title: string;
  subtitle?: string;
  rows: Row[];
  emptyLabel: string;
  labelKey?: (row: Row) => string;
  className?: string;
};

export default function DistributionBarChart({
  title,
  subtitle,
  rows,
  emptyLabel,
  labelKey = (row) => row.label,
  className,
}: Props) {
  const max = Math.max(...rows.map((r) => r.count), 1);

  return (
    <article className={cn("an-distribution-card", className)}>
      <header className="an-distribution-card__header">
        <h3 className="an-distribution-card__title">{title}</h3>
        {subtitle && <p className="an-distribution-card__subtitle">{subtitle}</p>}
      </header>
      {rows.length === 0 ? (
        <p className="an-chart-card__empty">{emptyLabel}</p>
      ) : (
        <ul className="an-distribution-list">
          {rows.map((row) => (
            <li key={labelKey(row)} className="an-distribution-row">
              <div className="an-distribution-row__meta">
                <span className="an-distribution-row__label">{labelKey(row)}</span>
                <span className="an-distribution-row__value">
                  {row.count} · {(row.share * 100).toFixed(1)}%
                </span>
              </div>
              <div className="an-distribution-row__track">
                <span
                  className="an-distribution-row__bar"
                  style={{ width: `${Math.max((row.count / max) * 100, 4)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
