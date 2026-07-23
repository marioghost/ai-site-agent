import type { ReactNode } from "react";
import { StatusBadge, healthStatusToBadge } from "../../ui";
import { IconExternal } from "./icons";

export type SubsystemItemKind = "status" | "link" | "text";

export interface SubsystemItem {
  id: string;
  name: string;
  icon: ReactNode;
  kind: SubsystemItemKind;
  status?: string;
  statusLabel?: string;
  /** Optional secondary line shown under a status badge (truncated, full text on hover). */
  detail?: string | null;
  href?: string | null;
  text?: string | null;
  emptyLabel?: string;
}

export interface SubsystemGroup {
  id: string;
  title: string;
  items: SubsystemItem[];
}

interface Props {
  title: string;
  groups: SubsystemGroup[];
}

function SubsystemItemRow({ item }: { item: SubsystemItem }) {
  return (
    <div
      className="ov-subsystem-item"
      title={item.kind === "status" ? item.detail?.trim() || undefined : undefined}
    >
      <div className="ov-subsystem-item__icon">{item.icon}</div>
      <div className="ov-subsystem-item__body">
        <span className="ov-subsystem-item__name">{item.name}</span>
        {item.kind === "status" && item.status != null && item.statusLabel != null && (
          <StatusBadge
            variant={healthStatusToBadge(item.status)}
            label={item.statusLabel}
            size="sm"
          />
        )}
        {item.kind === "link" &&
          (item.href?.trim() ? (
            <a
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              className="ov-subsystem-item__link"
              title={item.href}
            >
              <span className="ov-subsystem-item__detail">{item.href}</span>
              <IconExternal size={14} />
            </a>
          ) : (
            <span className="ov-subsystem-item__detail ov-subsystem-item__detail--muted">
              {item.emptyLabel ?? "—"}
            </span>
          ))}
        {item.kind === "text" && (
          <span className="ov-subsystem-item__detail" title={item.text?.trim() || undefined}>
            {item.text?.trim() ? item.text : item.emptyLabel ?? "—"}
          </span>
        )}
      </div>
    </div>
  );
}

export default function SubsystemHealthPanel({ title, groups }: Props) {
  const visibleGroups = groups.filter((group) => group.items.length > 0);
  if (visibleGroups.length === 0) return null;

  return (
    <section className="ds-section-card">
      <div className="ds-section-card__header">
        <h3 className="ds-section-card__title">{title}</h3>
      </div>
      <div className="ds-section-card__body" style={{ paddingTop: 0 }}>
        <div className="ov-subsystem-grid">
          {visibleGroups.map((group) => (
            <article key={group.id} className="ov-subsystem-tile">
              <h4 className="ov-subsystem-tile__title">{group.title}</h4>
              <div className="ov-subsystem-list">
                {group.items.map((item) => (
                  <SubsystemItemRow key={item.id} item={item} />
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
