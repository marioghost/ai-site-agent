import type { UnderstandingTrace, UnderstandingTraceStep } from "../types";

const STEP_STATUSES = new Set(["pending", "skipped", "completed", "failed"]);

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asOptionalString(value: unknown): string | null | undefined {
  if (value == null) return value === null ? null : undefined;
  return String(value);
}

function asOptionalNumber(value: unknown): number | null | undefined {
  if (value == null) return value === null ? null : undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

export function normalizeUnderstandingTraceStep(
  raw: unknown,
  index: number
): UnderstandingTraceStep {
  const row = asRecord(raw) ?? {};
  const details = asRecord(row.details) ?? {};
  const statusRaw = String(row.status ?? "pending");
  const status = STEP_STATUSES.has(statusRaw)
    ? (statusRaw as UnderstandingTraceStep["status"])
    : "pending";

  return {
    phase: String(row.phase ?? `step-${index + 1}`),
    status,
    summary: asOptionalString(row.summary),
    duration_ms:
      asOptionalNumber(row.duration_ms) ?? asOptionalNumber(details.duration_ms),
    evidence_count:
      asOptionalNumber(row.evidence_count) ?? asOptionalNumber(details.evidence_count),
    confidence:
      asOptionalNumber(row.confidence) ?? asOptionalNumber(details.confidence),
    details,
  };
}

/** Parse API / persistence payloads safely; returns null when absent or invalid. */
export function normalizeUnderstandingTrace(raw: unknown): UnderstandingTrace | null {
  const row = asRecord(raw);
  if (!row) return null;

  const stepsRaw = row.steps;
  const steps = Array.isArray(stepsRaw)
    ? stepsRaw.map((step, index) => normalizeUnderstandingTraceStep(step, index))
    : [];

  return {
    version: String(row.version ?? "stub"),
    populated: Boolean(row.populated),
    summary: asOptionalString(row.summary),
    steps,
  };
}

/** Gate for the engineering diagnostics panel (RFC-100 Step 015). */
export function shouldShowUnderstandingTracePanel(
  semanticDiagnosticsV2Enabled: boolean,
  chatDebugEnabled: boolean,
  trace: UnderstandingTrace | null | undefined
): boolean {
  return semanticDiagnosticsV2Enabled && chatDebugEnabled && trace != null;
}

export function understandingTraceStepsCount(trace: UnderstandingTrace): number {
  return trace.steps?.length ?? 0;
}

export function understandingTraceHasSteps(trace: UnderstandingTrace): boolean {
  return understandingTraceStepsCount(trace) > 0;
}
