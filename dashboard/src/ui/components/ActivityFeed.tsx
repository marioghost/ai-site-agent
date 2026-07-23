import type { ReactNode } from "react";
import { Card, CardHeader, CardBody } from "./Card";
import { cn } from "../utils/cn";

export type ActivityEntry = {
  time: string;
  level?: string;
  message: string;
};

type Props = {
  items: ActivityEntry[];
  emptyLabel?: string;
  className?: string;
};

export function ActivityFeed({ items, emptyLabel = "No activity yet", className }: Props) {
  if (items.length === 0) {
    return <p className="ds-caption">{emptyLabel}</p>;
  }

  return (
    <div className={cn("ds-activity", className)}>
      {items.map((entry, i) => (
        <div
          key={`${entry.time}-${i}`}
          className={cn("ds-activity__item", entry.level === "error" && "ds-activity__item--error")}
        >
          <span className="ds-activity__dot" aria-hidden />
          <div className="ds-activity__content">
            <p className="ds-activity__text">{entry.message}</p>
            <time className="ds-activity__time">{entry.time}</time>
          </div>
        </div>
      ))}
    </div>
  );
}

export function LogViewer({ lines, className }: { lines: string[]; className?: string }) {
  return (
    <pre className={cn("ds-log-viewer", className)}>
      {lines.join("\n")}
    </pre>
  );
}

export function CodeBlock({ children, className }: { children: string; className?: string }) {
  return <pre className={cn("ds-code-block", className)}>{children}</pre>;
}

type Tab = { id: string; label: string };

type TabsProps = {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
};

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn("ds-tabs", className)}>
      <div className="ds-tabs__list" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            className={cn("ds-tabs__tab", active === tab.id && "ds-tabs__tab--active")}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}

type AccordionProps = {
  title: string;
  children: ReactNode;
  open?: boolean;
  onToggle?: () => void;
};

export function Accordion({ title, children, open = false, onToggle }: AccordionProps) {
  return (
    <Card padding="md">
      <button
        type="button"
        className="ds-btn ds-btn--ghost"
        style={{ width: "100%", justifyContent: "space-between", marginBottom: open ? "var(--ds-space-3)" : 0 }}
        onClick={onToggle}
        aria-expanded={open}
      >
        {title}
        <span aria-hidden>{open ? "−" : "+"}</span>
      </button>
      {open && <CardBody>{children}</CardBody>}
    </Card>
  );
}

export function InfoCard({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader title={title} />
      <CardBody>{children}</CardBody>
    </Card>
  );
}

export { StatCard } from "./MetricCard";
