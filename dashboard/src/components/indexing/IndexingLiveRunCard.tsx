import StatusIndicator from "../overview/StatusIndicator";
import type { IndexJobStatus } from "../../types";
import type { IndexStatusViewModel } from "../../lib/indexStatus";
import { computeRunVelocity, formatRemaining } from "../../lib/indexingRunStats";
import { HelpText, ProgressBar, SectionCard } from "../../ui";

type Props = {
  status: IndexJobStatus | null;
  live: IndexStatusViewModel;
  pendingOnlyRun: boolean;
  jobStatusLabel: (s: string) => string;
  t: (key: string, params?: Record<string, string | number>) => string;
  indexingStageLabel: (stage: string) => string;
};

function LiveStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="ds-index-live-stat">
      <span className="ds-index-live-stat__label">{label}</span>
      <strong className="ds-index-live-stat__value">{value}</strong>
    </div>
  );
}

function formatEtaSeconds(seconds: number | null | undefined): string | null {
  if (seconds == null || seconds <= 0) return null;
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function resolveRunTitle(
  status: IndexJobStatus | null,
  jobStatus: string,
  t: (key: string) => string
): string {
  const mode = status?.run_mode;
  const dryRun = status?.dry_run === true;
  if (mode === "source_intelligence") {
    if (jobStatus === "running") {
      return dryRun
        ? t("indexing.run.title_intelligence_estimate")
        : t("indexing.run.title_intelligence");
    }
    if (jobStatus === "completed") {
      return dryRun
        ? t("indexing.run.title_intelligence_estimate_done")
        : t("indexing.run.title_intelligence_done");
    }
    if (jobStatus === "failed" || jobStatus === "stopped") {
      return dryRun
        ? t("indexing.run.title_intelligence_estimate")
        : t("indexing.run.title_intelligence");
    }
    return t("indexing.run.title_intelligence");
  }
  if (mode === "reprocess") return t("indexing.run.title_reprocess");
  if (mode === "pending_only") return t("indexing.run.title_pending_only");
  if (status?.status === "running" || status?.status === "completed") {
    return t("indexing.run.title_indexing");
  }
  return t("indexing.run.title_idle");
}

function resolveRunSubtitle(
  status: IndexJobStatus | null,
  jobStatus: string,
  stageLabel: string,
  jobStatusLabel: (s: string) => string,
  t: (key: string, params?: Record<string, string | number>) => string
): string {
  if (jobStatus === "running") {
    return stageLabel;
  }
  if (jobStatus === "idle") {
    return t("indexing.run.waiting");
  }
  if (status?.run_mode === "source_intelligence" && jobStatus === "completed") {
    if (status.dry_run) {
      return t("indexing.run.intelligence_estimate_summary", {
        selected: status.intelligence_selected_sources ?? status.selected_sources ?? 0,
        skip: status.would_skip_unchanged ?? status.skipped_unchanged ?? 0,
        llm: status.would_call_llm ?? status.llm_calls ?? 0,
        updated: status.intelligence_updated_sources ?? 0,
      });
    }
    return t("indexing.run.intelligence_done_summary", {
      updated: status.intelligence_updated_sources ?? status.progress?.processed_total ?? 0,
      skipped: status.skipped_unchanged ?? 0,
      llm: status.llm_calls ?? 0,
    });
  }
  return jobStatusLabel(jobStatus);
}

export default function IndexingLiveRunCard({
  status,
  live,
  pendingOnlyRun,
  jobStatusLabel,
  indexingStageLabel,
  t,
}: Props) {
  const isReprocess = status?.run_mode === "reprocess";
  const isIntelligence = status?.run_mode === "source_intelligence";
  const isIndexing = !isReprocess && !isIntelligence;
  const stageLabel = indexingStageLabel(live.stage);
  const runTitle = resolveRunTitle(status, live.jobStatus, t);
  const runSubtitle = resolveRunSubtitle(
    status,
    live.jobStatus,
    stageLabel,
    jobStatusLabel,
    t
  );
  const intelligenceDryRunDone =
    isIntelligence && live.jobStatus === "completed" && status?.dry_run === true;

  const heartbeatKey =
    live.aliveState === "active"
      ? "indexing.run.heartbeat_active"
      : live.aliveState === "slow"
        ? "indexing.run.heartbeat_slow"
        : live.aliveState === "stuck"
          ? "indexing.run.heartbeat_stuck"
          : "indexing.run.heartbeat_unknown";

  const progressLabel = live.progress.isIndeterminate
    ? t("indexing.run.progress_indeterminate", { processed: live.progress.processedTotal })
    : t("indexing.run.progress_determinate", {
        processed: live.progress.processedTotal,
        selected: live.progress.selectedTotal,
      });

  const barPercent =
    live.progress.percent ??
    (live.progress.selectedTotal > 0
      ? Math.min(
          100,
          Math.round((live.progress.processedTotal / live.progress.selectedTotal) * 100)
        )
      : live.jobStatus === "completed"
        ? 100
        : null);

  const { pagesPerMin, etaLabel } = computeRunVelocity(status, live);
  const remaining = formatRemaining(live.progress.selectedTotal, live.progress.processedTotal);
  const intelligenceEta = formatEtaSeconds(status?.estimated_remaining_seconds);

  const showProgress =
    live.jobStatus === "running" ||
    (live.progress.selectedTotal > 0 && live.progress.processedTotal > 0);

  return (
    <SectionCard
      title={runTitle}
      subtitle={runSubtitle}
      actions={
        <StatusIndicator status={live.jobStatus} label={jobStatusLabel(live.jobStatus)} />
      }
    >
      {pendingOnlyRun && live.jobStatus === "running" && isIndexing && (
        <p className="ds-pending-run-note">{t("indexing.run.pending_only_note")}</p>
      )}

      <div className="ds-index-live">
        {showProgress && (
          <div className="ds-index-live__progress-row">
            <ProgressBar
              className="ds-index-live__progress-bar"
              label={progressLabel}
              percent={barPercent}
              indeterminate={live.progress.isIndeterminate && live.jobStatus === "running"}
            />
          </div>
        )}

        <div className="ds-index-live__body">
          <div className="ds-index-live__main">
            {live.jobStatus === "running" && (
              <HelpText>{t(heartbeatKey, { seconds: live.secondsSinceActivity ?? 0 })}</HelpText>
            )}

            {live.currentUrl ? (
              <div className="ds-index-live__url">
                <span className="ds-caption">{t("indexing.run.current_url")}</span>
                <a
                  href={live.currentUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="ds-index-live__url-link"
                >
                  {live.currentUrl}
                </a>
                {live.currentAction && (
                  <HelpText>
                    {t("indexing.run.current_action")}: {live.currentAction}
                  </HelpText>
                )}
              </div>
            ) : live.lastActivityMessage && live.jobStatus === "running" ? (
              <HelpText>{live.lastActivityMessage}</HelpText>
            ) : live.jobStatus === "idle" ? (
              <HelpText>{t("indexing.run.waiting")}</HelpText>
            ) : null}

            {live.jobStatus === "failed" && (
              <p className="ds-run-error">
                {status?.log_tail?.slice().reverse().find((e) => e.level === "error")?.message ||
                  live.lastActivityMessage ||
                  t("indexing.run.failed_generic")}
              </p>
            )}
          </div>

          <div className="ds-index-live__stats">
            {isIntelligence ? (
              <>
                <LiveStat
                  label={t("indexing.live.processed")}
                  value={`${live.progress.processedTotal}${live.progress.selectedTotal > 0 ? ` / ${live.progress.selectedTotal}` : ""}`}
                />
                <LiveStat
                  label={
                    intelligenceDryRunDone
                      ? t("indexing.intelligence.would_skip")
                      : t("indexing.intelligence.skipped")
                  }
                  value={
                    intelligenceDryRunDone
                      ? (status?.would_skip_unchanged ?? status?.skipped_unchanged ?? 0)
                      : (status?.skipped_unchanged ?? 0)
                  }
                />
                <LiveStat
                  label={t("indexing.intelligence.cache_hits")}
                  value={status?.llm_cache_hits ?? 0}
                />
                <LiveStat
                  label={
                    intelligenceDryRunDone
                      ? t("indexing.intelligence.would_call_llm")
                      : t("indexing.intelligence.llm_calls")
                  }
                  value={
                    intelligenceDryRunDone
                      ? (status?.would_call_llm ?? status?.llm_calls ?? 0)
                      : (status?.llm_calls ?? 0)
                  }
                />
                {!intelligenceDryRunDone && (
                  <LiveStat
                    label={t("indexing.summary.updated")}
                    value={status?.intelligence_updated_sources ?? live.summary.updated}
                  />
                )}
                {live.jobStatus === "running" && (
                  <LiveStat
                    label={t("indexing.live.eta")}
                    value={intelligenceEta ?? etaLabel ?? "—"}
                  />
                )}
              </>
            ) : isReprocess ? (
              <>
                <LiveStat
                  label={t("indexing.live.processed")}
                  value={`${live.progress.processedTotal}${live.progress.selectedTotal > 0 ? ` / ${live.progress.selectedTotal}` : ""}`}
                />
                <LiveStat label={t("indexing.live.remaining")} value={remaining ?? "—"} />
                <LiveStat label={t("indexing.summary.updated")} value={live.summary.updated} />
                <LiveStat label={t("indexing.summary.skipped")} value={live.summary.skipped} />
                <LiveStat label={t("indexing.summary.errors")} value={live.summary.errors} />
                <LiveStat
                  label={t("indexing.live.pages_per_min")}
                  value={pagesPerMin != null ? pagesPerMin : "—"}
                />
                <LiveStat label={t("indexing.live.eta")} value={etaLabel ?? "—"} />
              </>
            ) : (
              <>
                <LiveStat
                  label={t("indexing.live.processed")}
                  value={`${live.progress.processedTotal}${live.progress.selectedTotal > 0 ? ` / ${live.progress.selectedTotal}` : ""}`}
                />
                <LiveStat label={t("indexing.live.remaining")} value={remaining ?? "—"} />
                <LiveStat label={t("indexing.summary.updated")} value={live.summary.updated} />
                <LiveStat label={t("indexing.summary.skipped")} value={live.summary.skipped} />
                <LiveStat label={t("indexing.summary.errors")} value={live.summary.errors} />
                <LiveStat
                  label={t("indexing.live.queue_size")}
                  value={live.queue.queuedForRun || live.queue.totalWaiting || "—"}
                />
                <LiveStat
                  label={t("indexing.live.pages_per_min")}
                  value={pagesPerMin != null ? pagesPerMin : "—"}
                />
                <LiveStat label={t("indexing.live.eta")} value={etaLabel ?? "—"} />
              </>
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}
