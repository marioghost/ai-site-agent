import { useRef, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../ui/utils/cn";

export type KvItem = { label: string; value: ReactNode; mono?: boolean };

export function KvGrid({ items }: { items: KvItem[] }) {
  return (
    <dl className="ds-kv-grid">
      {items.map((item) => (
        <div key={item.label} className="ds-kv-grid__row">
          <dt>{item.label}</dt>
          <dd className={item.mono ? "ds-kv-grid__mono" : undefined}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function MetricPills({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <div className="ds-metric-pills">
      {items.map((item) => (
        <div key={item.label} className="ds-metric-pill">
          <span className="ds-metric-pill__label">{item.label}</span>
          <span className="ds-metric-pill__value">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

type DiagnosticSectionProps = {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  badge?: ReactNode;
};

export function DiagnosticSection({
  title,
  children,
  defaultOpen = true,
  badge,
}: DiagnosticSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const sectionRef = useRef<HTMLElement>(null);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      if (next) {
        requestAnimationFrame(() => {
          sectionRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
      }
      return next;
    });
  };

  return (
    <section ref={sectionRef} className={cn("ds-diag-card", open && "ds-diag-card--open")}>
      <button
        type="button"
        className="ds-diag-card__header"
        onClick={toggle}
        aria-expanded={open}
      >
        <span className="ds-diag-card__title">{title}</span>
        <span className="ds-diag-card__meta">
          {badge}
          <ChevronDown size={16} className={cn("ds-diag-card__chevron", open && "is-open")} />
        </span>
      </button>
      {open && <div className="ds-diag-card__body">{children}</div>}
    </section>
  );
}

export function asList(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (value == null || value === "") return "—";
  return String(value);
}
