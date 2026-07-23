import { useTranslation } from "../../i18n";
import type { TracePayload, TraceStep } from "../../types";
import { DiagnosticSection } from "./DiagnosticSection";

function useFormatMs() {
  const { t, lang } = useTranslation();
  return (ms: number): string => {
    if (ms >= 1000) return t("common.seconds", { value: (ms / 1000).toFixed(2) });
    return lang === "uk" ? `${ms} мс` : t("common.ms", { value: ms });
  };
}

function stepStatusIcon(status: string): string {
  if (status === "error") return "error";
  if (status === "skipped") return "skipped";
  return "ok";
}

function detailSummary(step: TraceStep, t: (key: string, params?: Record<string, string | number>) => string): string {
  const d = step.details;
  if (!d || Object.keys(d).length === 0) return "";
  const parts: string[] = [];
  if (d.hit === true) parts.push(t("trace.detail.cache_yes"));
  if (d.hit === false) parts.push(t("trace.detail.cache_no"));
  if (typeof d.normalized === "string") parts.push(String(d.normalized));
  if (typeof d.hits === "number") parts.push(t("trace.detail.found", { value: d.hits }));
  if (typeof d.chunks === "number") parts.push(t("trace.detail.chunks", { value: d.chunks }));
  if (typeof d.kept === "number") parts.push(t("trace.detail.kept", { value: d.kept }));
  if (typeof d.sources === "number") parts.push(t("trace.detail.sources", { value: d.sources }));
  if (typeof d.reason === "string") parts.push(String(d.reason));
  if (Array.isArray(d.variants))
    parts.push(t("trace.detail.variants", { value: (d.variants as string[]).join(", ") }));
  if (typeof d.error === "string") parts.push(String(d.error));
  return parts.join(" · ");
}

export default function ChatSearchPipeline({ trace }: { trace: TracePayload }) {
  const { t, traceStepLabel, traceStatusLabel } = useTranslation();
  const formatMs = useFormatMs();
  const totalMs = trace.steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0);

  return (
    <DiagnosticSection
      title={t("trace.title")}
      defaultOpen
      badge={
        totalMs > 0 ? (
          <span className="ds-diag-card__badge">{formatMs(totalMs)}</span>
        ) : undefined
      }
    >
      <ol className="ds-pipeline">
        {trace.steps.map((step, i) => {
          const status = stepStatusIcon(step.status);
          const details = detailSummary(step, t);
          return (
            <li key={`${step.name}-${i}`} className={`ds-pipeline__step ds-pipeline__step--${status}`}>
              <span className="ds-pipeline__icon" aria-hidden />
              <div className="ds-pipeline__content">
                <div className="ds-pipeline__row">
                  <span className="ds-pipeline__name">{traceStepLabel(step.name)}</span>
                  {step.duration_ms > 0 && (
                    <span className="ds-pipeline__duration">{formatMs(step.duration_ms)}</span>
                  )}
                </div>
                <div className="ds-pipeline__meta">
                  {traceStatusLabel(step.status)}
                  {details && <> · {details}</>}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </DiagnosticSection>
  );
}
