import type { ReactNode } from "react";
import { cn } from "../utils/cn";

type Props = {
  children: ReactNode;
  actions?: ReactNode;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  collapseLabel?: ReactNode;
  /** Bordered card surface for filter panels. */
  elevated?: boolean;
  className?: string;
};

export function FilterBar({
  children,
  actions,
  collapsed = false,
  onToggleCollapse,
  collapseLabel,
  elevated = false,
  className,
}: Props) {
  const shellClass = cn(
    "ds-filter-bar",
    elevated && "ds-filter-bar--elevated",
    collapsed && "ds-filter-bar--collapsed",
    className
  );

  if (collapsed) {
    return (
      <div className={shellClass}>
        {onToggleCollapse && (
          <button type="button" className="ds-btn ds-btn--ghost ds-btn--sm" onClick={onToggleCollapse}>
            {collapseLabel}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={shellClass}>
      <div className="ds-filter-bar__fields">{children}</div>
      {(actions || onToggleCollapse) && (
        <div className="ds-filter-bar__actions">
          {actions}
          {onToggleCollapse && collapseLabel && (
            <button type="button" className="ds-btn ds-btn--ghost ds-btn--sm" onClick={onToggleCollapse}>
              {collapseLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
