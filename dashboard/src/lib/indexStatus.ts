/** Map nested indexing status API to UI view-model counters. */
import type { IndexJobStatus, IndexQueuePreview } from "../types";

export interface IndexStatusViewModel {
  jobStatus: string;
  stage: string;
  currentUrl: string | null;
  currentUrlType: string | null;
  currentAction: string | null;
  lastActivityAt: string | null;
  lastActivityMessage: string | null;
  heartbeatCounter: number;
  aliveState: string;
  secondsSinceActivity: number | null;
  progress: {
    selectedTotal: number;
    processedTotal: number;
    selectedPages: number;
    selectedFiles: number;
    processedPages: number;
    processedFiles: number;
    percent: number | null;
    isIndeterminate: boolean;
  };
  summary: {
    foundPages: number;
    foundFiles: number;
    selectedPages: number;
    selectedFiles: number;
    processedPages: number;
    processedFiles: number;
    added: number;
    updated: number;
    unchanged: number;
    skipped: number;
    errors: number;
  };
  recentActivity: { time: string; level: string; message: string }[];
  discovery: {
    discoveredUrls: number;
    newlyDiscoveredUrls: number;
    discoveredFiles: number;
  };
  queue: {
    newPagesWaiting: number;
    failedPagesWaiting: number;
    stalePagesWaiting: number;
    freshSkipped: number;
    queuedForRun: number;
    totalWaiting: number;
  };
  pages: {
    processed: number;
    indexedNew: number;
    updated: number;
    unchanged: number;
    skippedEmpty: number;
    skippedFresh: number;
    failed: number;
  };
  files: {
    discovered: number;
    indexed: number;
    skipped: number;
    failed: number;
  };
  errors: number;
  jobId: number | null;
  rawPhase: string;
}

export interface IndexQueuePreviewViewModel {
  newPagesWaiting: number;
  failedPagesWaiting: number;
  stalePagesWaiting: number;
  freshSkipped: number;
  skippedPagesWaiting: number;
  totalWaiting: number;
  queuedForRun: number;
  maxPagesPerRun: number;
  estimatedRunsRemaining: number;
}

const num = (value: number | undefined | null): number =>
  typeof value === "number" && !Number.isNaN(value) ? value : 0;

export function mapIndexStatusToViewModel(
  status: IndexJobStatus | null
): IndexStatusViewModel {
  const d = status?.discovery;
  const q = status?.queue;
  const p = status?.pages;
  const f = status?.files;
  const prog = status?.progress;
  const sum = status?.summary;

  return {
    jobStatus: status?.status ?? "idle",
    stage: status?.stage ?? status?.current_phase ?? status?.status ?? "idle",
    currentUrl: status?.current_url ?? null,
    currentUrlType: status?.current_url_type ?? null,
    currentAction: status?.current_action ?? null,
    lastActivityAt: status?.last_activity_at ?? status?.updated_at ?? null,
    lastActivityMessage: status?.last_activity_message ?? null,
    heartbeatCounter: num(status?.heartbeat_counter),
    aliveState: status?.alive_state ?? "unknown",
    secondsSinceActivity:
      status?.seconds_since_activity != null
        ? num(status.seconds_since_activity)
        : null,
    progress: {
      selectedTotal: num(prog?.selected_total),
      processedTotal: num(prog?.processed_total),
      selectedPages: num(prog?.selected_pages),
      selectedFiles: num(prog?.selected_files),
      processedPages: num(prog?.processed_pages ?? p?.processed_pages),
      processedFiles: num(prog?.processed_files ?? f?.processed_files),
      percent: prog?.percent ?? null,
      isIndeterminate: prog?.is_indeterminate ?? true,
    },
    summary: {
      foundPages: num(sum?.found_pages ?? d?.discovered_pages),
      foundFiles: num(sum?.found_files ?? f?.discovered_files),
      selectedPages: num(sum?.selected_pages ?? q?.queued_pages_for_this_run),
      selectedFiles: num(sum?.selected_files ?? f?.queued_files_for_this_run),
      processedPages: num(sum?.processed_pages ?? p?.processed_pages),
      processedFiles: num(sum?.processed_files ?? f?.processed_files),
      added: num(sum?.added),
      updated: num(sum?.updated),
      unchanged: num(sum?.unchanged),
      skipped: num(sum?.skipped),
      errors: num(sum?.errors ?? status?.errors_count),
    },
    recentActivity: (status?.recent_activity ?? status?.log_tail ?? []).map(
      (e) => ({
        time: "time" in e ? e.time : e.timestamp,
        level: e.level,
        message: e.message,
      })
    ),
    discovery: {
      discoveredUrls: num(d?.discovered_urls ?? status?.discovered_pages),
      newlyDiscoveredUrls: num(d?.newly_discovered_urls ?? status?.new_pages),
      discoveredFiles: num(f?.discovered_files ?? status?.discovered_files),
    },
    queue: {
      newPagesWaiting: num(q?.new_pages_waiting ?? status?.new_pages),
      failedPagesWaiting: num(q?.failed_pages_waiting),
      stalePagesWaiting: num(q?.stale_pages_waiting ?? status?.stale_pages),
      freshSkipped: num(
        q?.fresh_pages_skipped_until_refresh ?? status?.skipped_fresh_pages
      ),
      queuedForRun: num(q?.queued_pages_for_this_run ?? status?.queued_pages),
      totalWaiting: num(q?.total_pages_waiting),
    },
    pages: {
      processed: num(p?.processed_pages ?? status?.processed_pages),
      indexedNew: num(p?.indexed_new_pages ?? status?.indexed_pages),
      updated: num(p?.updated_pages),
      unchanged: num(p?.unchanged_pages ?? status?.unchanged_pages),
      skippedEmpty: num(p?.skipped_empty_pages ?? status?.skipped_pages),
      skippedFresh: num(p?.skipped_fresh_pages ?? status?.skipped_fresh_pages),
      failed: num(p?.failed_pages ?? status?.failed_pages),
    },
    files: {
      discovered: num(f?.discovered_files ?? status?.discovered_files),
      indexed: num(
        (f?.indexed_new_files ?? 0) + (f?.updated_files ?? 0) ||
          status?.indexed_files
      ),
      skipped: num(f?.skipped_files ?? status?.skipped_files),
      failed: num(f?.failed_files),
    },
    errors: num(status?.errors_count),
    jobId: status?.id ?? null,
    rawPhase: status?.current_phase ?? "idle",
  };
}

export function mapQueuePreviewToViewModel(
  preview: IndexQueuePreview | null
): IndexQueuePreviewViewModel {
  const q = preview?.queue;
  return {
    newPagesWaiting: num(q?.new_pages_waiting ?? preview?.new_pages),
    failedPagesWaiting: num(q?.failed_pages_waiting ?? preview?.failed_pages),
    stalePagesWaiting: num(q?.stale_pages_waiting ?? preview?.stale_pages),
    freshSkipped: num(
      q?.fresh_pages_skipped_until_refresh ?? preview?.fresh_pages
    ),
    totalWaiting: num(q?.total_pages_waiting ?? preview?.queued_pages),
    queuedForRun: num(q?.queued_pages_for_this_run),
    skippedPagesWaiting: num(preview?.skipped_pages_waiting),
    maxPagesPerRun: num(preview?.max_pages_per_run),
    estimatedRunsRemaining: num(preview?.estimated_runs_remaining),
  };
}

export function computeClientProgressPercent(
  selectedTotal: number,
  processedTotal: number
): { percent: number | null; isIndeterminate: boolean } {
  if (selectedTotal > 0) {
    return {
      percent: Math.min(100, Math.round((processedTotal / selectedTotal) * 1000) / 10),
      isIndeterminate: false,
    };
  }
  return { percent: null, isIndeterminate: true };
}
