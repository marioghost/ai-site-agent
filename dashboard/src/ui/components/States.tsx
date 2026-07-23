import type { ReactNode } from "react";
import { Inbox, AlertTriangle } from "lucide-react";

type EmptyProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
};

export function EmptyState({ title, description, action, icon }: EmptyProps) {
  return (
    <div className="ds-empty-state">
      <div className="ds-empty-state__icon">{icon ?? <Inbox size={28} />}</div>
      <h3 className="ds-empty-state__title">{title}</h3>
      {description && <p className="ds-empty-state__desc">{description}</p>}
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="ds-loading-state">
      <div className="ds-spinner" role="status" aria-label={label} />
      <p className="ds-caption">{label}</p>
    </div>
  );
}

type ErrorProps = {
  title?: string;
  description?: string;
  action?: ReactNode;
  details?: string;
};

export function ErrorState({
  title = "An error occurred",
  description,
  action,
  details,
}: ErrorProps) {
  return (
    <div className="ds-error-state">
      <div className="ds-error-state__icon">
        <AlertTriangle size={28} />
      </div>
      <h3 className="ds-error-state__title">{title}</h3>
      {description && <p className="ds-error-state__desc">{description}</p>}
      {action}
      {details && (
        <details style={{ marginTop: 12, textAlign: "left", width: "100%", maxWidth: 480 }}>
          <summary className="ds-caption">Technical details</summary>
          <pre className="ds-log-viewer" style={{ marginTop: 8 }}>
            {details}
          </pre>
        </details>
      )}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%", className }: { height?: number; width?: number | string; className?: string }) {
  return (
    <div
      className={`ds-skeleton ${className ?? ""}`}
      style={{ height, width }}
      aria-hidden
    />
  );
}
