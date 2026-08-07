import { useEffect, useRef, useState } from "react";
import {
  generateSourceIntelligence,
  getIndexStatus,
  getSettings,
  stopIndexing,
} from "../../../api/client";
import { useTranslation } from "../../../i18n";
import type { IndexJobStatus, Settings, SourceSemanticProfile } from "../../../types";
import { LoadingState, PageHeader, PageLayout } from "../../../ui";
import SourceIntelligencePanel from "./widgets/SourceIntelligencePanel";
import SourceIntelligencePreviewModal from "./widgets/SourceIntelligencePreviewModal";

/**
 * S006 (G4-P4) — Engineering owner for Source Intelligence generate/preview
 * chrome. Previously mounted on the product `/knowledge/update` surface;
 * relocated here so Update stays focused on the indexing job itself. Reuses
 * the same generate/dry-run/preview APIs, polling the shared index job
 * status (Update's Start/Stop reflects the same job when SI runs).
 */
export default function EngKnowledgeScreen() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState<IndexJobStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
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

  const refresh = async () => {
    try {
      const st = await getIndexStatus();
      setStatus(st);
    } catch {
      // Ignore transient polling errors.
    }
  };

  useEffect(() => {
    getSettings().then(setSettings);
    void refresh();
  }, []);

  useEffect(() => {
    const running = status?.status === "running";
    const intervalMs = running ? 3000 : 15000;
    timer.current = window.setInterval(() => void refresh(), intervalMs);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [status?.status]);

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

  const onStopIntelligence = async () => {
    setMessage(null);
    setIntelligenceError(null);
    try {
      const res = await stopIndexing();
      setMessage(res.message || t("indexing.actions.intelligence_stopped"));
      await refresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      const detail = err?.response?.data?.detail || t("indexing.error.stop");
      setMessage(detail);
      setIntelligenceError(detail);
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

  if (!settings) return <LoadingState label={t("common.loading_settings")} />;

  return (
    <PageLayout className="ds-page--wide">
      <PageHeader title={t("nav.eng_knowledge")} subtitle={t("eng.knowledge.subtitle")} />

      {message && <p className="ds-help">{message}</p>}

      <SourceIntelligencePanel
        status={status}
        llmEnabled={Boolean(settings.enable_llm_source_intelligence)}
        busy={intelligenceBusy}
        errorMessage={intelligenceError}
        onGenerateMissing={() => void onGenerateIntelligence(false, "needs_intelligence")}
        onReprocessAll={() => void onGenerateIntelligence(false, "all")}
        onDryRun={() => void onGenerateIntelligence(true, "needs_intelligence")}
        onStop={() => void onStopIntelligence()}
        t={t}
      />

      <SourceIntelligencePreviewModal
        open={intelligencePreviewOpen}
        onClose={() => setIntelligencePreviewOpen(false)}
        profiles={intelligencePreviewProfiles}
        total={intelligencePreviewTotal}
      />
    </PageLayout>
  );
}
