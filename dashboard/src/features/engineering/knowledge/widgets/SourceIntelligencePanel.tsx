import {
  AlertTriangle,
  BrainCircuit,
  ChevronDown,
  Play,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getSourceIntelligenceStats } from "../../../../api/client";
import { Button, HelpText, MetricCard, MetricGrid, SectionCard } from "../../../../ui";

type Stats = {
  sources_needing_intelligence: number;
  sources_up_to_date: number;
  total_indexed: number;
  estimated_llm_calls: number;
  estimated_skips: number;
  worker_count: number;
  batch_size: number;
  page_size: number;
  llm_enabled?: boolean;
};

type Props = {
  status: {
    run_mode?: string | null;
    status?: string;
  } | null;
  llmEnabled?: boolean;
  onGenerateMissing: () => void;
  onReprocessAll: () => void;
  onDryRun: () => void;
  onStop?: () => void;
  busy: boolean;
  errorMessage?: string | null;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export default function SourceIntelligencePanel({
  status,
  llmEnabled = false,
  onGenerateMissing,
  onReprocessAll,
  onDryRun,
  onStop,
  busy,
  errorMessage,
  t,
}: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState(false);
  const [perfOpen, setPerfOpen] = useState(false);

  const isRunning =
    status?.run_mode === "source_intelligence" && status?.status === "running";

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getSourceIntelligenceStats()
        .then((data) => {
          if (!cancelled) {
            setStats(data);
            setStatsError(false);
          }
        })
        .catch(() => {
          if (!cancelled) setStatsError(true);
        });
    };
    load();
    const id = window.setInterval(load, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [isRunning]);

  const needs = stats?.sources_needing_intelligence ?? 0;
  const upToDate = stats?.sources_up_to_date ?? 0;
  const allCurrent = needs === 0 && (stats?.total_indexed ?? 0) > 0;
  const warnLarge = llmEnabled && needs > 100;
  const warnWorkers = (stats?.worker_count ?? 1) > 2;

  return (
    <SectionCard
      title={t("indexing.intelligence.panel_title")}
      subtitle={t("indexing.intelligence.panel_intro")}
      actions={
        <span className="ds-intel-panel__badge" aria-hidden>
          <BrainCircuit size={16} />
          {llmEnabled
            ? t("indexing.intelligence.mode_llm")
            : t("indexing.intelligence.mode_rules")}
        </span>
      }
    >
      <div className="ds-intel-panel">
        <p className="ds-intel-panel__intro">{t("indexing.intelligence.panel_what")}</p>

        {statsError && (
          <div className="ds-intel-panel__alert ds-intel-panel__alert--muted" role="status">
            {t("indexing.intelligence.stats_unavailable")}
          </div>
        )}

        {errorMessage && (
          <div className="ds-intel-panel__alert ds-intel-panel__alert--error" role="alert">
            <AlertTriangle size={16} aria-hidden />
            <span>{errorMessage}</span>
          </div>
        )}

        {allCurrent && !isRunning && (
          <div className="ds-intel-panel__alert ds-intel-panel__alert--success" role="status">
            <Sparkles size={16} aria-hidden />
            <span>{t("indexing.intelligence.all_current", { total: stats?.total_indexed ?? 0 })}</span>
          </div>
        )}

        <div className="ds-intel-panel__stats-heading">{t("indexing.intelligence.stats_heading")}</div>
        <HelpText className="ds-intel-panel__stats-hint">{t("indexing.intelligence.stats_hint")}</HelpText>

        <MetricGrid columns={3} className="ds-intel-panel__metrics">
          <MetricCard
            label={t("indexing.intelligence.needs_update")}
            value={stats ? needs : "—"}
            tone={needs > 0 ? "warning" : "success"}
            icon={<RefreshCw size={16} />}
            helper={
              stats
                ? t("indexing.intelligence.needs_update_hint", { total: stats.total_indexed })
                : undefined
            }
          />
          <MetricCard
            label={t("indexing.intelligence.up_to_date")}
            value={stats ? upToDate : "—"}
            tone="success"
            icon={<Zap size={16} />}
            helper={t("indexing.intelligence.up_to_date_hint")}
          />
          <MetricCard
            label={t("indexing.intelligence.estimated_llm")}
            value={stats ? stats.estimated_llm_calls : "—"}
            tone={llmEnabled ? "info" : "neutral"}
            icon={<Sparkles size={16} />}
            helper={
              llmEnabled
                ? t("indexing.intelligence.estimated_llm_hint")
                : t("indexing.intelligence.llm_disabled_hint")
            }
          />
        </MetricGrid>

        <details
          className="ds-intel-panel__perf"
          open={perfOpen}
          onToggle={(e) => setPerfOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="ds-intel-panel__perf-toggle">
            {t("indexing.intelligence.perf_settings_title")}
            <ChevronDown size={16} aria-hidden className="ds-intel-panel__perf-chevron" />
          </summary>
          <HelpText>{t("indexing.intelligence.perf_settings_intro")}</HelpText>
          <dl className="ds-intel-panel__perf-list">
            <div className="ds-intel-panel__perf-row">
              <dt>{t("indexing.intelligence.worker_count")}</dt>
              <dd>
                <strong>{stats?.worker_count ?? "—"}</strong>
                <span>{t("indexing.intelligence.worker_count_hint")}</span>
              </dd>
            </div>
            <div className="ds-intel-panel__perf-row">
              <dt>{t("indexing.intelligence.batch_size")}</dt>
              <dd>
                <strong>{stats?.batch_size ?? "—"}</strong>
                <span>{t("indexing.intelligence.batch_size_hint")}</span>
              </dd>
            </div>
            <div className="ds-intel-panel__perf-row">
              <dt>{t("indexing.intelligence.page_size")}</dt>
              <dd>
                <strong>{stats?.page_size ?? "—"}</strong>
                <span>{t("indexing.intelligence.page_size_hint")}</span>
              </dd>
            </div>
          </dl>
        </details>

        {(warnLarge || warnWorkers) && (
          <div className="ds-intel-panel__alert ds-intel-panel__alert--warn" role="status">
            <AlertTriangle size={16} aria-hidden />
            <div>
              {warnLarge && <p>{t("indexing.intelligence.warn_large_batch")}</p>}
              {warnWorkers && <p>{t("indexing.intelligence.warn_many_workers")}</p>}
            </div>
          </div>
        )}

        <div className="ds-intel-panel__actions-heading">{t("indexing.intelligence.actions_heading")}</div>
        <div className="ds-intel-panel__actions">
          <Button disabled={busy || isRunning} onClick={onGenerateMissing} aria-busy={isRunning}>
            <Play size={16} aria-hidden />
            {isRunning
              ? t("indexing.intelligence.action_running")
              : t("indexing.intelligence.action_missing")}
          </Button>
          {onStop ? (
            <Button variant="danger" disabled={!isRunning} onClick={onStop}>
              {t("indexing.intelligence.action_stop")}
            </Button>
          ) : null}
          <Button variant="secondary" disabled={busy || isRunning} onClick={onReprocessAll}>
            <RefreshCw size={16} aria-hidden />
            {t("indexing.intelligence.action_reprocess_all")}
          </Button>
          <Button variant="ghost" disabled={busy || isRunning} onClick={onDryRun}>
            {t("indexing.intelligence.action_estimate")}
          </Button>
        </div>

        <HelpText>{t("indexing.intelligence.actions_hint")}</HelpText>
      </div>
    </SectionCard>
  );
}
