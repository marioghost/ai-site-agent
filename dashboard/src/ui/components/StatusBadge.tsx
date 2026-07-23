import { cn } from "../utils/cn";

export type StatusVariant =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "info"
  | "ready"
  | "pending"
  | "processing"
  | "failed"
  | "skipped"
  | "needs_refresh"
  | "queued"
  | "running"
  | "stopped"
  | "completed";

type Props = {
  variant: StatusVariant;
  label: string;
  size?: "sm" | "md";
};

export function StatusBadge({ variant, label, size = "sm" }: Props) {
  return (
    <span className={cn("ds-badge", `ds-badge--${variant}`, size === "md" && "ds-badge--md")}>
      {label}
    </span>
  );
}

/** Map common backend status strings to badge variants. */
export function statusToVariant(status: string): StatusVariant {
  const s = status.toLowerCase();
  const map: Record<string, StatusVariant> = {
    ready: "ready",
    indexed: "ready",
    pending: "pending",
    new: "pending",
    processing: "processing",
    running: "running",
    error: "failed",
    failed: "failed",
    skipped: "skipped",
    needs_refresh: "needs_refresh",
    stale: "needs_refresh",
    queued: "queued",
    stopped: "stopped",
    completed: "completed",
    idle: "stopped",
  };
  return map[s] ?? "pending";
}

/** Map health/subsystem status strings (ok, warn, err) to badge variants. */
export function healthStatusToBadge(status: string): StatusVariant {
  const h = status.toLowerCase();
  const map: Record<string, StatusVariant> = {
    ok: "ready",
    online: "ready",
    indexed: "ready",
    completed: "ready",
    running: "running",
    pending: "pending",
    warn: "processing",
    warning: "processing",
    degraded: "processing",
    idle: "stopped",
    stopped: "stopped",
    skipped: "skipped",
    muted: "skipped",
    unknown: "skipped",
    error: "failed",
    err: "failed",
    failed: "failed",
    unavailable: "failed",
  };
  return map[h] ?? statusToVariant(status);
}
