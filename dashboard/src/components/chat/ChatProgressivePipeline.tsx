import { useTranslation } from "../../i18n";
import type { PipelineStage } from "../../chat/types";
import { DiagnosticSection } from "./DiagnosticSection";

function useFormatMs() {
  const { t, lang } = useTranslation();
  return (ms: number): string => {
    if (ms >= 1000) return t("common.seconds", { value: (ms / 1000).toFixed(2) });
    return lang === "uk" ? `${ms} мс` : t("common.ms", { value: ms });
  };
}

function statusClass(status: PipelineStage["status"]): string {
  if (status === "running") return "running";
  if (status === "completed") return "ok";
  if (status === "error") return "error";
  if (status === "skipped") return "skipped";
  return "pending";
}

export default function ChatProgressivePipeline({ stages }: { stages: PipelineStage[] }) {
  const { t, traceStepLabel } = useTranslation();
  const formatMs = useFormatMs();
  const visible = stages.filter((s) => s.status !== "pending");
  if (!visible.length) return null;

  return (
    <DiagnosticSection title={t("trace.title")} defaultOpen>
      <ol className="ds-pipeline">
        {stages.map((step) => {
          const status = statusClass(step.status);
          if (step.status === "pending") return null;
          return (
            <li key={step.id} className={`ds-pipeline__step ds-pipeline__step--${status}`}>
              <span className="ds-pipeline__icon" aria-hidden />
              <div className="ds-pipeline__content">
                <div className="ds-pipeline__row">
                  <span className="ds-pipeline__name">{traceStepLabel(step.name)}</span>
                  {step.durationMs != null && step.durationMs > 0 && (
                    <span className="ds-pipeline__duration">{formatMs(step.durationMs)}</span>
                  )}
                  {step.status === "running" && (
                    <span className="ds-pipeline__duration">{t("chat.metric_waiting")}</span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </DiagnosticSection>
  );
}
