export type StatusVariant = "ok" | "warn" | "err" | "muted";

const STATUS_MAP: Record<string, StatusVariant> = {
  ok: "ok",
  indexed: "ok",
  completed: "ok",
  online: "ok",
  running: "warn",
  pending: "warn",
  warning: "warn",
  degraded: "warn",
  idle: "muted",
  skipped: "muted",
  stopped: "muted",
  error: "err",
  failed: "err",
  unavailable: "err",
  unknown: "muted",
};

export function statusToVariant(status: string): StatusVariant {
  return STATUS_MAP[status] ?? "muted";
}
