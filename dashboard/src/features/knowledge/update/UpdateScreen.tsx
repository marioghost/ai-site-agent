import { useCallback, useEffect, useRef, useState } from "react";
import {
  generateSourceIntelligence,
  getIndexQueuePreview,
  getIndexStatus,
  getSettings,
  reindexAll,
  reprocessExisting,
  startIndexing,
  stopIndexing,
  updateSettings,
} from "../../../api/client";
import IndexingActionsBar from "./widgets/IndexingActionsBar";
import IndexingActivitySection from "./widgets/IndexingActivitySection";
import IndexingConfigCard from "./widgets/IndexingConfigCard";
import IndexingHelpAccordion from "./widgets/IndexingHelpAccordion";
import IndexingInfoBanner from "./widgets/IndexingInfoBanner";
import IndexingLiveRunCard from "./widgets/IndexingLiveRunCard";
import IndexingNextStepsGrid from "./widgets/IndexingNextStepsGrid";
import IndexingQueueCard from "./widgets/IndexingQueueCard";
import SourceIntelligencePanel from "./widgets/SourceIntelligencePanel";
import SourceIntelligencePreviewModal from "./widgets/SourceIntelligencePreviewModal";
import OverviewHeader from "../../../components/overview/OverviewHeader";
import StatusIndicator from "../../../components/overview/StatusIndicator";
import { useTranslation } from "../../../i18n";
import { mapIndexStatusToViewModel, mapQueuePreviewToViewModel } from "../../../lib/indexStatus";
import type {
  IndexJobStatus,
  IndexQueuePreview,
  Settings,
  SourceSemanticProfile,
} from "../../../types";
import { LoadingState, PageLayout } from "../../../ui";

export default function UpdateScreen() {
  const { t, jobStatusLabel, indexingStageLabel, lang } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState<IndexJobStatus | null>(null);
  const [queuePreview, setQueuePreview] = useState<IndexQueuePreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [showAdvancedSetup, setShowAdvancedSetup] = useState(false);
  const [intelligencePreviewOpen, setIntelligencePreviewOpen] = useState(false);
  const [intelligencePreviewProfiles, setIntelligencePreviewProfiles] = useState<
    Array<{
      url?: string;
      title?: string;
      semantic?: SourceSemanticProfile | Record<string, unknown>;
      llm_summary?: string;
      profile_version?: string;
    }>
  >([]);
  const [intelligencePreviewTotal, setIntelligencePreviewTotal] = useState(0);
  const [intelligenceTask, setIntelligenceTask] = useState<"generate" | "preview" | null>(null);
  const [intelligenceError, setIntelligenceError] = useState<string | null>(null);
  const completedIntelligenceJobRef = useRef<number | null>(null);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async (opts?: { includeQueue?: boolean }) => {
    setRefreshing(true);
    try {
      const st = await getIndexStatus();
      setStatus(st);
      const running = st.status === "running";
      if (opts?.includeQueue || !running) {
        const qp = await getIndexQueuePreview();
        setQueuePreview(qp);
      }
      setLastUpdated(new Date());
    } catch {
      // Ignore transient polling errors.
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    getSettings().then(setSettings);
    void refresh({ includeQueue: true });
  }, [refresh]);

  useEffect(() => {
    const running = status?.status === "running";
    const intervalMs = running ? 3000 : 15000;
    timer.current = window.setInterval(() => void refresh({ includeQueue: !running }), intervalMs);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [refresh, status?.status]);

  const intelligenceRunning =
    status?.run_mode === "source_intelligence" && status?.status === "running";
  const intelligenceBusy = intelligenceRunning || intelligenceTask != null;

  useEffect(() => {
    if (!intelligenceTask) return;
    const timeout = window.setTimeout(() => setIntelligenceTask(null), 120_000);
    return () => window.clearTimeout(timeout);
  }, [intelligenceTask]);

  useEffect(() => {
    if (!intelligenceTask || !status) return;
    if (status.run_mode !== "source_intelligence") return;
    if (status.status === "running") return;
    if (!["completed", "failed", "stopped"].includes(status.status)) return;
    if (status.id != null && completedIntelligenceJobRef.current === status.id) return;
    if (status.id != null) {
      completedIntelligenceJobRef.current = status.id;
    }

    if (status.status === "completed") {
      if (intelligenceTask === "preview") {
        const dry = status.dry_run === true;
        if (dry) {
          setMessage(
            t("indexing.intelligence.dry_run_result", {
              selected: status.intelligence_selected_sources ?? status.selected_sources ?? 0,
              skip: status.would_skip_unchanged ?? status.skipped_unchanged ?? 0,
              llm: status.would_call_llm ?? status.llm_calls ?? 0,
              seconds: status.estimated_time_with_llm ?? status.estimated_remaining_seconds ?? 0,
            })
          );
        } else {
          const rawProfiles = status.intelligence_sample_profiles ?? [];
          setIntelligencePreviewProfiles(
            rawProfiles.map((sample) => {
              const row = sample as Record<string, unknown>;
              return {
                url: typeof row.url === "string" ? row.url : undefined,
                title: typeof row.title === "string" ? row.title : undefined,
                semantic:
                  (row.semantic as SourceSemanticProfile | Record<string, unknown>) ?? undefined,
                llm_summary: typeof row.llm_summary === "string" ? row.llm_summary : undefined,
                profile_version:
                  typeof row.profile_version === "string" ? row.profile_version : undefined,
              };
            })
          );
          setIntelligencePreviewTotal(status.intelligence_selected_sources ?? rawProfiles.length);
          setIntelligencePreviewOpen(true);
          setMessage(
            t("indexing.actions.intelligence_preview_result", {
              count: status.intelligence_selected_sources ?? rawProfiles.length,
            })
          );
        }
      } else {
        setMessage(
          t("indexing.actions.intelligence_result", {
            count: status.intelligence_updated_sources ?? status.progress?.processed_total ?? 0,
          })
        );
      }
    } else if (status.status === "failed") {
      const err =
        status.log_tail?.slice().reverse().find((e) => e.level === "error")?.message ??
        t("indexing.actions.intelligence_failed");
      setMessage(err);
    } else {
      setMessage(t("indexing.actions.intelligence_stopped"));
    }

    setIntelligenceTask(null);
  }, [status, intelligenceTask, t]);

  if (!settings) return <LoadingState label={t("common.loading_settings")} />;

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings({ ...settings, [key]: value });

  const persistSettings = async (): Promise<Settings> => {
    const saved = await updateSettings(settings);
    setSettings(saved);
    return saved;
  };

  const onStart = async () => {
    setMessage(null);
    setBusy(true);
    try {
      await persistSettings();
      const res = await startIndexing({});
      setMessage(res.message);
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("indexing.error.start"));
    } finally {
      setBusy(false);
    }
  };

  const onStop = async () => {
    setMessage(null);
    try {
      const res = await stopIndexing();
      setMessage(res.message);
      setIntelligenceTask(null);
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("indexing.error.stop"));
    }
  };

  const onReprocessExisting = async (dryRun = false) => {
    if (
      !confirm(
        dryRun ? t("indexing.actions.reprocess_preview_confirm") : t("indexing.actions.reprocess_confirm")
      )
    ) {
      return;
    }
    setMessage(null);
    setBusy(true);
    try {
      const res = await reprocessExisting({
        scope: "by_filter",
        dry_run: dryRun,
      });
      setMessage(
        dryRun
          ? t("indexing.actions.reprocess_preview_result", {
              count: res.selected_sources,
              chunks: res.estimated_chunks ?? 0,
            })
          : t("indexing.actions.reprocess_started", { job: res.job_id, count: res.selected_sources })
      );
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("indexing.actions.reprocess_failed"));
    } finally {
      setBusy(false);
    }
  };

  const onGenerateIntelligence = async (
    dryRun = false,
    scope: "needs_intelligence" | "all" = "needs_intelligence"
  ) => {
    if (
      !confirm(
        dryRun
          ? t("indexing.actions.intelligence_preview_confirm")
          : scope === "all"
            ? `${t("indexing.intelligence.action_reprocess_all")}?`
            : t("indexing.actions.intelligence_confirm")
      )
    ) {
      return;
    }
    setMessage(null);
    setIntelligenceError(null);
    setIntelligenceTask(dryRun ? "preview" : "generate");
    try {
      const res = await generateSourceIntelligence({
        scope,
        dry_run: dryRun,
        generate_summaries: dryRun ? false : Boolean(settings?.enable_llm_source_intelligence),
      });
      if (!dryRun && res.selected_sources === 0) {
        setIntelligenceError(t("indexing.intelligence.empty_needs_hint"));
        setIntelligenceTask(null);
        return;
      }
      setMessage(
        t("indexing.actions.intelligence_started", {
          count: res.selected_sources,
          mode: dryRun
            ? t("indexing.actions.intelligence_mode_preview")
            : t("indexing.actions.intelligence_mode_generate"),
        })
      );
      await refresh();
      window.setTimeout(() => void refresh(), 400);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      const detail = err?.response?.data?.detail || t("indexing.actions.intelligence_failed");
      setMessage(detail);
      setIntelligenceError(detail);
      setIntelligenceTask(null);
    }
  };

  const onReindexAll = async () => {
    if (!confirm(t("indexing.run.reindex_confirm"))) return;
    setMessage(null);
    setBusy(true);
    try {
      await persistSettings();
      const res = await reindexAll();
      setMessage(res.message);
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("indexing.error.reindex"));
    } finally {
      setBusy(false);
    }
  };

  const running = status?.status === "running";
  const pendingOnlyRun = status?.run_mode === "pending_only";
  const actionBusy = busy || intelligenceRunning || intelligenceTask != null;
  const live = mapIndexStatusToViewModel(status);
  const queue = mapQueuePreviewToViewModel(queuePreview);
  const recentActivity = live.recentActivity.slice().reverse();

  return (
    <PageLayout>
      <OverviewHeader
        title={t("knowledge.update.title")}
        subtitle={t("knowledge.update.subtitle")}
        updatedAt={lastUpdated}
        updatedLabel={t("indexing.updated")}
        refreshLabel={t("common.refresh")}
        onRefresh={() => void refresh()}
        refreshing={refreshing}
        status={<StatusIndicator status={live.jobStatus} label={jobStatusLabel(live.jobStatus)} />}
      />

      <IndexingInfoBanner
        text={t("indexing.info.short")}
        docLabel={t("indexing.info.docs_link")}
      />

      <IndexingConfigCard
        settings={settings}
        update={update}
        showAdvanced={showAdvancedSetup}
        onToggleAdvanced={setShowAdvancedSetup}
        t={t}
        actions={
          <IndexingActionsBar
            running={running}
            busy={actionBusy}
            intelligenceRunning={intelligenceRunning || intelligenceTask != null}
            intelligenceMode={intelligenceTask}
            message={message}
            onStart={() => void onStart()}
            onStop={() => void onStop()}
            onReindexAll={() => void onReindexAll()}
            onReprocess={() => void onReprocessExisting(false)}
            onGenerateIntelligence={() => void onGenerateIntelligence(false, "needs_intelligence")}
            onReprocessPreview={() => void onReprocessExisting(true)}
            onIntelligencePreview={() => void onGenerateIntelligence(true, "needs_intelligence")}
            t={t}
          />
        }
      />

      <IndexingLiveRunCard
        status={status}
        live={live}
        pendingOnlyRun={pendingOnlyRun}
        jobStatusLabel={jobStatusLabel}
        indexingStageLabel={indexingStageLabel}
        t={t}
      />

      <SourceIntelligencePanel
        status={status}
        llmEnabled={Boolean(settings.enable_llm_source_intelligence)}
        busy={intelligenceBusy}
        errorMessage={intelligenceError}
        onGenerateMissing={() => void onGenerateIntelligence(false, "needs_intelligence")}
        onReprocessAll={() => void onGenerateIntelligence(false, "all")}
        onDryRun={() => void onGenerateIntelligence(true, "needs_intelligence")}
        t={t}
      />

      <IndexingQueueCard queue={queue} live={live} lang={lang} t={t} />
      <IndexingActivitySection entries={recentActivity} t={t} />
      <IndexingNextStepsGrid live={live} t={t} />

      <div id="indexing-help">
        <IndexingHelpAccordion settings={settings} t={t} />
      </div>

      <SourceIntelligencePreviewModal
        open={intelligencePreviewOpen}
        onClose={() => setIntelligencePreviewOpen(false)}
        profiles={intelligencePreviewProfiles}
        total={intelligencePreviewTotal}
      />
    </PageLayout>
  );
}
