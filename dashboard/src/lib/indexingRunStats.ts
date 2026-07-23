import type { IndexJobStatus } from "../types";
import type { IndexStatusViewModel } from "./indexStatus";

export function computeRunVelocity(
  status: IndexJobStatus | null,
  live: IndexStatusViewModel
): { pagesPerMin: number | null; etaLabel: string | null } {
  if (!status?.started_at || live.jobStatus !== "running") {
    return { pagesPerMin: null, etaLabel: null };
  }
  const started = new Date(status.started_at).getTime();
  const elapsedMin = (Date.now() - started) / 60000;
  if (elapsedMin < 0.05 || live.progress.processedTotal <= 0) {
    return { pagesPerMin: null, etaLabel: null };
  }
  const ppm = live.progress.processedTotal / elapsedMin;
  const remaining = Math.max(0, live.progress.selectedTotal - live.progress.processedTotal);
  let etaLabel: string | null = null;
  if (remaining > 0 && ppm > 0 && live.progress.selectedTotal > 0) {
    const etaSec = Math.round((remaining / ppm) * 60);
    if (etaSec < 60) etaLabel = `${etaSec}s`;
    else if (etaSec < 3600) etaLabel = `${Math.round(etaSec / 60)}m`;
    else etaLabel = `${Math.round(etaSec / 3600)}h`;
  }
  return { pagesPerMin: Math.round(ppm * 10) / 10, etaLabel };
}

export function formatRemaining(
  selectedTotal: number,
  processedTotal: number
): number | null {
  if (selectedTotal <= 0) return null;
  return Math.max(0, selectedTotal - processedTotal);
}
