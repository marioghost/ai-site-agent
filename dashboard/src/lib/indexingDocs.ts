import type { IndexStatusViewModel } from "./indexStatus";
import type { Settings } from "../types";

type Translate = (key: string, params?: Record<string, string | number>) => string;

export function buildIndexingDocHints(settings: Settings, t: Translate): string[] {
  const hints: string[] = [];

  if (settings.scan_mode === "pages_only") {
    hints.push(t("indexing.docs.hint_pages_only"));
  } else if (settings.scan_mode === "pages_and_files") {
    hints.push(t("indexing.docs.hint_pages_and_files"));
  } else {
    hints.push(t("indexing.docs.hint_files_only"));
  }

  if (settings.enable_file_indexing && settings.scan_mode !== "pages_only") {
    const types = settings.allowed_file_types.map((x) => x.toUpperCase()).join(", ");
    hints.push(t("indexing.docs.hint_file_types", { types: types || "—" }));
  }

  if (settings.scan_all_pages) {
    hints.push(t("indexing.docs.hint_scan_all"));
  } else if (settings.max_pages_per_run > 0) {
    hints.push(
      t("indexing.docs.hint_max_pages", { max: settings.max_pages_per_run })
    );
  }

  hints.push(
    t("indexing.docs.hint_refresh", {
      hours: settings.indexed_page_refresh_interval_hours,
    })
  );

  return hints;
}

export function buildNextStepHints(
  live: IndexStatusViewModel,
  t: Translate
): string[] {
  const steps: string[] = [];
  const done = ["completed", "stopped", "failed"].includes(live.jobStatus);

  if (live.summary.errors > 0) {
    steps.push(t("indexing.next.check_errors"));
  }

  if (done && live.summary.processedPages + live.summary.processedFiles === 0) {
    steps.push(t("indexing.next.zero_processed"));
  }

  if (live.queue.freshSkipped > 0 && live.jobStatus === "completed") {
    steps.push(t("indexing.next.many_skipped_fresh"));
  }

  if (done && live.summary.added + live.summary.updated > 0) {
    steps.push(t("indexing.next.check_sources"));
    steps.push(t("indexing.next.test_chat"));
    steps.push(t("indexing.next.check_profile"));
  } else if (done) {
    steps.push(t("indexing.next.check_sources"));
  }

  if (live.summary.errors === 0 && done) {
    steps.push(t("indexing.next.reindex_if_needed"));
  }

  return steps;
}
