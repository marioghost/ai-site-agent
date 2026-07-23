import { useState } from "react";
import { Copy } from "lucide-react";
import type { UnderstandingTrace, UnderstandingTraceStep } from "../../types";
import { understandingTraceHasSteps } from "../../lib/understandingTrace";
import { Button } from "../../ui";
import { DiagnosticSection, KvGrid } from "./DiagnosticSection";

type Props = {
  trace: UnderstandingTrace;
};

function StepRow({ step, index }: { step: UnderstandingTraceStep; index: number }) {
  const [jsonOpen, setJsonOpen] = useState(false);

  return (
    <li className="ds-understanding-trace__step">
      <div className="ds-understanding-trace__step-header">
        <span className="ds-understanding-trace__step-phase">
          {step.phase || `step-${index + 1}`}
        </span>
        <span className={`ds-understanding-trace__status ds-understanding-trace__status--${step.status}`}>
          {step.status}
        </span>
      </div>
      <KvGrid
        items={[
          { label: "Phase", value: step.phase || `step-${index + 1}` },
          { label: "Status", value: step.status },
          {
            label: "Duration",
            value: step.duration_ms != null ? `${step.duration_ms} ms` : "—",
          },
          { label: "Summary", value: step.summary ?? "—" },
          {
            label: "Evidence count",
            value: step.evidence_count != null ? String(step.evidence_count) : "—",
          },
          {
            label: "Confidence",
            value: step.confidence != null ? String(step.confidence) : "—",
          },
        ]}
      />
      <button
        type="button"
        className="ds-understanding-trace__json-toggle"
        onClick={() => setJsonOpen((open) => !open)}
        aria-expanded={jsonOpen}
      >
        {jsonOpen ? "Hide JSON" : "Show JSON"}
      </button>
      {jsonOpen && (
        <pre className="ds-understanding-trace__json">{JSON.stringify(step, null, 2)}</pre>
      )}
    </li>
  );
}

export default function UnderstandingTracePanel({ trace }: Props) {
  const [copied, setCopied] = useState(false);
  const steps = trace.steps ?? [];
  const hasSteps = understandingTraceHasSteps(trace);

  const onCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(trace, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <DiagnosticSection
      title="Understanding Trace (Experimental)"
      defaultOpen={false}
      badge={<span className="ds-diag-card__badge">{steps.length}</span>}
    >
      <KvGrid
        items={[
          { label: "Version", value: trace.version ?? "—", mono: true },
          { label: "Populated", value: trace.populated ? "yes" : "no" },
          { label: "Steps count", value: String(steps.length) },
        ]}
      />

      {!hasSteps ? (
        <p className="ds-understanding-trace__empty">
          No semantic reasoning has been executed yet.
        </p>
      ) : (
        <ol className="ds-understanding-trace__steps">
          {steps.map((step, index) => (
            <StepRow key={`${step.phase}-${index}`} step={step} index={index} />
          ))}
        </ol>
      )}

      <div className="ds-understanding-trace__actions">
        <Button type="button" variant="secondary" size="sm" onClick={() => void onCopyJson()}>
          <Copy size={14} aria-hidden />
          {copied ? "Copied" : "Copy JSON"}
        </Button>
      </div>
    </DiagnosticSection>
  );
}
