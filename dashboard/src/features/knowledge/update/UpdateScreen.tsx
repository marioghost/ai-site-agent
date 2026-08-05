import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
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
import OverviewHeader from "../../../components/overview/OverviewHeader";
import StatusIndicator from "../../../components/overview/StatusIndicator";
import { useEngineeringMode } from "../../../context/EngineeringModeContext";
import { useTranslation } from "../../../i18n";
import { mapIndexStatusToViewModel, mapQueuePreviewToViewModel } from "../../../lib/indexStatus";
import type { IndexJobStatus, IndexQueuePreview, Settings } from "../../../types";
import { Button, LoadingState, PageLayout, SectionCard } from "../../../ui";

export default function UpdateScreen() {
  const { t, jobStatusLabel, indexingStageLabel, lang } = useTranslation();
  const { enabled: engineeringModeOn } = useEngineeringMode();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState<IndexJobStatus | null>(null);
  const [queuePreview, setQueuePreview] = useState<IndexQueuePreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [showAdvancedSetup, setShowAdvancedSetup] = useState(false);
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
  const actionBusy = busy;
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
            message={message}
            onStart={() => void onStart()}
            onStop={() => void onStop()}
            onReindexAll={() => void onReindexAll()}
            onReprocess={() => void onReprocessExisting(false)}
            onReprocessPreview={() => void onReprocessExisting(true)}
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

      {engineeringModeOn && (
        <SectionCard title={t("indexing.intelligence.eng_link_title")}>
          <p className="ds-help">{t("indexing.intelligence.eng_link_body")}</p>
          <Link to="/engineering/knowledge">
            <Button variant="secondary">{t("indexing.intelligence.eng_link_cta")}</Button>
          </Link>
        </SectionCard>
      )}

      <IndexingQueueCard queue={queue} live={live} lang={lang} t={t} />
      <IndexingActivitySection entries={recentActivity} t={t} />
      <IndexingNextStepsGrid live={live} t={t} />

      <div id="indexing-help">
        <IndexingHelpAccordion settings={settings} t={t} />
      </div>
    </PageLayout>
  );
}
