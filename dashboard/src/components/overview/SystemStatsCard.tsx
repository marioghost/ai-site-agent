import type { ReactNode } from "react";

export interface StatItem {
  id: string;
  label: string;
  value: string | number;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  icon: ReactNode;
  iconTone: string;
}

interface Props {
  title: string;
  items: StatItem[];
}

export default function SystemStatsCard({ title, items }: Props) {
  return (
    <article className="ov-analytics-card ov-analytics-card--stats">
      <h3 className="ov-analytics-card__title">{title}</h3>
      <div className="ov-stats-grid">
        {items.map((item) => (
          <div key={item.id} className="ov-stat-item">
            <div className={`ov-stat-item__icon ov-stat-item__icon--${item.iconTone}`}>
              {item.icon}
            </div>
            <div className="ov-stat-item__body">
              <span className="ov-stat-item__label">{item.label}</span>
              <span className="ov-stat-item__value">{item.value}</span>
              {item.delta && (
                <span className={`ov-stat-item__delta ov-stat-item__delta--${item.deltaTone ?? "neutral"}`}>
                  {item.delta}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
