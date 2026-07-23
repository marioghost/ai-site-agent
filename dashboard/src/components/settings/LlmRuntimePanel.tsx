import {
  Activity,
  Cpu,
  Gauge,
  MemoryStick,
  Play,
  RefreshCw,
  Sparkles,
  Thermometer,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getLlmRuntimeInfo, pullOllamaModel, runLlmBenchmark } from "../../api/client";
import { useTranslation } from "../../i18n";
import type { LlmBenchmarkResponse, LlmBenchmarkScenario, LlmRuntimeInfo } from "../../types";
import { Alert, Button, HelpText, MetricCard, MetricGrid, SectionCard, StatusBadge } from "../../ui";

const BENCHMARK_CACHE_KEY = "ai_agent_llm_benchmark_last";

type Props = {
  /** Full panel on Settings; compact summary on Overview */
  variant?: "settings" | "overview";
};

function formatMs(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function tpsTone(tps: number): "success" | "warning" | "danger" | "neutral" {
  if (tps >= 15) return "success";
  if (tps >= 5) return "warning";
  if (tps > 0) return "danger";
  return "neutral";
}

function ttftTone(ms: number | null | undefined): "success" | "warning" | "danger" | "neutral" {
  if (ms == null) return "neutral";
  if (ms < 3000) return "success";
  if (ms < 10000) return "warning";
  return "danger";
}

function warmupTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "warm") return "success";
  if (status === "warming") return "info";
  if (status === "failed") return "danger";
  return "warning";
}

function TimingBar({
  load,
  promptEval,
  evalMs,
  total,
}: {
  load: number;
  promptEval: number;
  evalMs: number;
  total: number;
}) {
  const safeTotal = Math.max(total, 1);
  const segments = [
    { key: "load", value: load, className: "ds-llm-bench__bar-seg--load" },
    { key: "prompt", value: promptEval, className: "ds-llm-bench__bar-seg--prompt" },
    { key: "eval", value: evalMs, className: "ds-llm-bench__bar-seg--eval" },
  ];
  return (
    <div className="ds-llm-bench__bar" aria-hidden>
      {segments.map((seg) => (
        <div
          key={seg.key}
          className={`ds-llm-bench__bar-seg ${seg.className}`}
          style={{ width: `${Math.max(0, (seg.value / safeTotal) * 100)}%` }}
        />
      ))}
    </div>
  );
}

function ScenarioCard({
  scenario,
  label,
}: {
  scenario: LlmBenchmarkScenario;
  label: string;
}) {
  const { t } = useTranslation();
  const load = scenario.load_duration_ms ?? 0;
  const promptEval = scenario.prompt_eval_duration_ms ?? 0;
  const evalMs = scenario.eval_duration_ms ?? 0;
  const total = scenario.total_duration_ms || load + promptEval + evalMs;

  if (scenario.error) {
    return (
      <article className="ds-llm-bench__scenario ds-llm-bench__scenario--error">
        <div className="ds-llm-bench__scenario-head">
          <h4>{label}</h4>
          <StatusBadge variant="failed" label={t("llm.benchmark.failed")} />
        </div>
        <p className="ds-llm-bench__scenario-error">{scenario.error}</p>
      </article>
    );
  }

  return (
    <article className="ds-llm-bench__scenario">
      <div className="ds-llm-bench__scenario-head">
        <h4>{label}</h4>
        <span className={`ds-llm-bench__tps ds-llm-bench__tps--${tpsTone(scenario.tokens_per_second)}`}>
          {scenario.tokens_per_second} tok/s
        </span>
      </div>
      <div className="ds-llm-bench__scenario-metrics">
        <div>
          <span className="ds-llm-bench__metric-label">{t("llm.benchmark.ttft")}</span>
          <strong className={`ds-llm-bench__metric-value ds-llm-bench__metric-value--${ttftTone(scenario.time_to_first_token_ms)}`}>
            {formatMs(scenario.time_to_first_token_ms)}
          </strong>
        </div>
        <div>
          <span className="ds-llm-bench__metric-label">{t("llm.benchmark.total")}</span>
          <strong className="ds-llm-bench__metric-value">{formatMs(scenario.total_duration_ms)}</strong>
        </div>
      </div>
      <TimingBar load={load} promptEval={promptEval} evalMs={evalMs} total={total} />
      <div className="ds-llm-bench__legend">
        <span><i className="ds-llm-bench__dot ds-llm-bench__dot--load" /> {t("llm.benchmark.load")} {formatMs(load)}</span>
        <span><i className="ds-llm-bench__dot ds-llm-bench__dot--prompt" /> {t("llm.benchmark.prompt_eval")} {formatMs(promptEval)}</span>
        <span><i className="ds-llm-bench__dot ds-llm-bench__dot--eval" /> {t("llm.benchmark.generation")} {formatMs(evalMs)}</span>
      </div>
      {scenario.answer_preview && (
        <p className="ds-llm-bench__preview" title={scenario.answer_preview}>
          {scenario.answer_preview}
        </p>
      )}
    </article>
  );
}

export default function LlmRuntimePanel({ variant = "settings" }: Props) {
  const { t } = useTranslation();
  const compact = variant === "overview";
  const [runtime, setRuntime] = useState<LlmRuntimeInfo | null>(null);
  const [benchmark, setBenchmark] = useState<LlmBenchmarkResponse | null>(() => {
    try {
      const raw = sessionStorage.getItem(BENCHMARK_CACHE_KEY);
      return raw ? (JSON.parse(raw) as LlmBenchmarkResponse) : null;
    } catch {
      return null;
    }
  });
  const [loadingRuntime, setLoadingRuntime] = useState(true);
  const [running, setRunning] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuntime = useCallback(async () => {
    setLoadingRuntime(true);
    try {
      const info = await getLlmRuntimeInfo();
      setRuntime(info);
      setError(null);
    } catch {
      setError(t("llm.benchmark.runtime_error"));
    } finally {
      setLoadingRuntime(false);
    }
  }, [t]);

  useEffect(() => {
    void loadRuntime();
  }, [loadRuntime]);

  const onInstallActiveModel = async () => {
    if (!runtime?.active_model) return;
    setInstalling(true);
    setError(null);
    try {
      await pullOllamaModel(runtime.active_model);
      void loadRuntime();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || t("settings.models.pull_error"));
    } finally {
      setInstalling(false);
    }
  };

  const onRunBenchmark = async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await runLlmBenchmark();
      setBenchmark(result);
      sessionStorage.setItem(BENCHMARK_CACHE_KEY, JSON.stringify(result));
      void loadRuntime();
    } catch {
      setError(t("llm.benchmark.run_error"));
    } finally {
      setRunning(false);
    }
  };

  const scenarioLabels: Record<string, string> = useMemo(
    () => ({
      tiny: t("llm.benchmark.scenario_tiny"),
      short_uk: t("llm.benchmark.scenario_short_uk"),
      rag_like: t("llm.benchmark.scenario_rag"),
    }),
    [t]
  );

  const env = runtime?.environment ?? {};
  const warmupStatus = String(runtime?.warmup?.status ?? benchmark?.warmup_status ?? "cold");
  const warmupError = runtime?.warmup?.error ? String(runtime.warmup.error) : null;
  const modelInstalled = runtime?.model_installed !== false;
  const runtimeMode = String(env.runtime_mode ?? "cpu").toUpperCase();
  const isGpu = Boolean(env.nvidia_gpu_visible);

  const ragScenario = benchmark?.scenarios.find((s) => s.key === "rag_like");
  const headlineTps = ragScenario?.tokens_per_second ?? benchmark?.scenarios[0]?.tokens_per_second;

  return (
    <SectionCard
      title={t("llm.benchmark.title")}
      subtitle={compact ? t("llm.benchmark.subtitle_overview") : t("llm.benchmark.subtitle")}
      actions={
        <div className="ds-llm-bench__actions">
          <Button variant="ghost" size="sm" onClick={() => void loadRuntime()} disabled={loadingRuntime}>
            <RefreshCw size={16} className={loadingRuntime ? "ds-spin" : undefined} />
            {t("common.refresh")}
          </Button>
          <Button variant="primary" size="sm" onClick={() => void onRunBenchmark()} disabled={running}>
            {running ? <RefreshCw size={16} className="ds-spin" /> : <Play size={16} />}
            {running ? t("llm.benchmark.running") : t("llm.benchmark.run")}
          </Button>
        </div>
      }
    >
      {error && <Alert variant="error">{error}</Alert>}
      {runtime && !modelInstalled && (
        <Alert variant="warning">
          {t("llm.benchmark.model_missing", { model: runtime.active_model })}
          {runtime.installed_models?.length ? (
            <span className="ds-llm-bench__installed">
              {" "}
              {t("llm.benchmark.installed_models", { models: runtime.installed_models.join(", ") })}
            </span>
          ) : null}
          <div className="ds-ollama-models__chips" style={{ marginTop: "0.5rem" }}>
            <Button variant="primary" size="sm" disabled={installing} onClick={() => void onInstallActiveModel()}>
              {installing ? t("settings.models.pulling") : t("llm.benchmark.install_model", { model: runtime.active_model })}
            </Button>
          </div>
        </Alert>
      )}
      {warmupStatus === "failed" && warmupError && (
        <Alert variant="error">{warmupError}</Alert>
      )}

      <div className="ds-llm-bench__hero">
        <div className="ds-llm-bench__hero-main">
          <div className="ds-llm-bench__hero-icon">
            <Sparkles size={22} />
          </div>
          <div>
            <div className="ds-llm-bench__hero-label">{t("llm.benchmark.active_model")}</div>
            <div className="ds-llm-bench__hero-model">{runtime?.active_model ?? "—"}</div>
            <div className="ds-llm-bench__hero-meta">
              <StatusBadge
                variant={runtime?.ollama_reachable ? "ready" : "failed"}
                label={runtime?.ollama_reachable ? t("llm.benchmark.ollama_ok") : t("llm.benchmark.ollama_down")}
              />
              <StatusBadge variant={warmupTone(warmupStatus)} label={t(`llm.benchmark.warmup_${warmupStatus}`)} />
              {runtime?.ollama_version && (
                <span className="ds-llm-bench__chip">Ollama {runtime.ollama_version}</span>
              )}
            </div>
          </div>
        </div>
        {headlineTps != null && (
          <div className="ds-llm-bench__hero-score">
            <Gauge size={18} />
            <span className="ds-llm-bench__hero-score-value">{headlineTps}</span>
            <span className="ds-llm-bench__hero-score-label">{t("llm.benchmark.last_tps")}</span>
          </div>
        )}
      </div>

      <MetricGrid columns={compact ? 4 : 6}>
        <MetricCard
          label={t("llm.benchmark.runtime_mode")}
          value={runtimeMode}
          icon={isGpu ? <Zap size={18} /> : <Cpu size={18} />}
          tone={isGpu ? "success" : "warning"}
          helper={isGpu ? t("llm.benchmark.gpu_hint") : t("llm.benchmark.cpu_hint")}
        />
        <MetricCard
          label={t("llm.benchmark.cpu_cores")}
          value={String(env.cpu_cores ?? "—")}
          icon={<Activity size={18} />}
          tone="info"
        />
        <MetricCard
          label={t("llm.benchmark.ram")}
          value={env.ram_mb ? `${Math.round(Number(env.ram_mb) / 1024)} GB` : "—"}
          icon={<MemoryStick size={18} />}
          tone="neutral"
        />
        <MetricCard
          label={t("llm.benchmark.keep_alive")}
          value={String(env.ollama_keep_alive_env ?? "30m")}
          icon={<Thermometer size={18} />}
          tone="neutral"
        />
        {!compact && (
          <>
            <MetricCard
              label="OLLAMA_NUM_PARALLEL"
              value={String(env.ollama_num_parallel ?? "—")}
              icon={<Zap size={18} />}
              tone="neutral"
            />
            <MetricCard
              label="OLLAMA_MAX_LOADED_MODELS"
              value={String(env.ollama_max_loaded_models ?? "—")}
              icon={<Zap size={18} />}
              tone="neutral"
            />
          </>
        )}
      </MetricGrid>

      {!benchmark && !running && (
        <div className="ds-llm-bench__empty">
          <Sparkles size={28} strokeWidth={1.5} />
          <p>{t("llm.benchmark.empty")}</p>
        </div>
      )}

      {running && (
        <div className="ds-llm-bench__running">
          <RefreshCw size={20} className="ds-spin" />
          <span>{t("llm.benchmark.running_detail")}</span>
        </div>
      )}

      {benchmark && !running && (
        <>
          <div className={`ds-llm-bench__scenarios${compact ? " ds-llm-bench__scenarios--compact" : ""}`}>
            {benchmark.scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.key}
                scenario={scenario}
                label={scenarioLabels[scenario.key] ?? scenario.key}
              />
            ))}
          </div>

          {!compact && (runtime?.recommended_models?.length ?? 0) > 0 && (
            <div className="ds-llm-bench__models">
              <h4 className="ds-llm-bench__models-title">{t("llm.benchmark.recommended_models")}</h4>
              <div className="ds-llm-bench__models-grid">
                {runtime?.recommended_models.map((m) => (
                  <div key={m.name} className="ds-llm-bench__model-card">
                    <div className="ds-llm-bench__model-name">{m.name}</div>
                    <div className="ds-llm-bench__model-tags">
                      <span className="ds-llm-bench__tag" title={t("llm.benchmark.tag_speed")}>
                        {t("llm.benchmark.speed")}: {m.speed}
                      </span>
                      <span className="ds-llm-bench__tag" title={t("llm.benchmark.tag_uk")}>
                        {t("llm.benchmark.ukrainian")}: {m.ukrainian}
                      </span>
                      <span className="ds-llm-bench__tag" title={t("llm.benchmark.tag_quality")}>
                        {t("llm.benchmark.quality")}: {m.quality}
                      </span>
                    </div>
                    <p className="ds-llm-bench__model-use">{m.use}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <HelpText>{t("llm.benchmark.help")}</HelpText>
    </SectionCard>
  );
}
