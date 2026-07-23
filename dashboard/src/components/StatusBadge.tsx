interface Props {
  status: string;
  /** Optional already-localized label. Falls back to the raw status. */
  label?: string;
}

const MAP: Record<string, string> = {
  ok: "ok",
  indexed: "ok",
  completed: "ok",
  running: "warn",
  pending: "warn",
  idle: "muted",
  skipped: "muted",
  stopped: "muted",
  error: "err",
  failed: "err",
};

export default function StatusBadge({ status, label }: Props) {
  const cls = MAP[status] ?? "muted";
  return <span className={`badge ${cls}`}>{label ?? status}</span>;
}
