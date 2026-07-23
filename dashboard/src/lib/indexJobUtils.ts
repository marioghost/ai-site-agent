import type { IndexJobStatus } from "../types";

/** Last error line from a failed indexing job, if any. */
export function indexJobErrorMessage(status: IndexJobStatus | null): string | null {
  if (!status || status.status !== "failed") return null;
  const entries = status.log_tail?.length ? status.log_tail : status.log ?? [];
  const err = [...entries].reverse().find((e) => e.level === "error");
  if (err?.message) return err.message;
  if (status.last_activity_message) return status.last_activity_message;
  return null;
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
