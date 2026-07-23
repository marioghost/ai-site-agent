import { describe, expect, it } from "vitest";
import { chatResponseFromDiagnostics } from "./chatTurnDiagnostics";
import {
  normalizeUnderstandingTrace,
  normalizeUnderstandingTraceStep,
  shouldShowUnderstandingTracePanel,
  understandingTraceHasSteps,
} from "./understandingTrace";
import type { ChatMessage } from "../types";

const EMPTY_STUB = {
  version: "stub",
  populated: false,
  summary: null,
  steps: [],
};

describe("understandingTrace", () => {
  it("shouldShowUnderstandingTracePanel is false when flag OFF", () => {
    expect(shouldShowUnderstandingTracePanel(false, true, EMPTY_STUB)).toBe(false);
    expect(shouldShowUnderstandingTracePanel(false, true, null)).toBe(false);
  });

  it("shouldShowUnderstandingTracePanel is false when flag ON but debug disabled", () => {
    expect(shouldShowUnderstandingTracePanel(true, false, EMPTY_STUB)).toBe(false);
    expect(shouldShowUnderstandingTracePanel(true, false, null)).toBe(false);
  });

  it("shouldShowUnderstandingTracePanel is false when trace absent", () => {
    expect(shouldShowUnderstandingTracePanel(true, true, null)).toBe(false);
    expect(shouldShowUnderstandingTracePanel(true, true, undefined)).toBe(false);
  });

  it("shouldShowUnderstandingTracePanel is true when flag ON, debug ON, trace present", () => {
    expect(shouldShowUnderstandingTracePanel(true, true, EMPTY_STUB)).toBe(true);
  });

  it("normalizeUnderstandingTrace returns null for absent trace", () => {
    expect(normalizeUnderstandingTrace(null)).toBeNull();
    expect(normalizeUnderstandingTrace(undefined)).toBeNull();
    expect(normalizeUnderstandingTrace("invalid")).toBeNull();
  });

  it("normalizeUnderstandingTrace parses empty stub", () => {
    const trace = normalizeUnderstandingTrace(EMPTY_STUB);
    expect(trace).not.toBeNull();
    expect(trace!.version).toBe("stub");
    expect(trace!.populated).toBe(false);
    expect(trace!.steps).toEqual([]);
    expect(understandingTraceHasSteps(trace!)).toBe(false);
  });

  it("normalizeUnderstandingTraceStep renders future populated fields gracefully", () => {
    const step = normalizeUnderstandingTraceStep(
      {
        phase: "intent_resolution",
        status: "completed",
        summary: "Resolved overview intent",
        duration_ms: 12,
        evidence_count: 3,
        confidence: 0.91,
        details: { model: "stub", extra: true },
      },
      0
    );
    expect(step.phase).toBe("intent_resolution");
    expect(step.status).toBe("completed");
    expect(step.summary).toBe("Resolved overview intent");
    expect(step.duration_ms).toBe(12);
    expect(step.evidence_count).toBe(3);
    expect(step.confidence).toBe(0.91);
    expect(step.details).toEqual({ model: "stub", extra: true });
  });

  it("normalizeUnderstandingTrace reads nested detail fallbacks for future schema", () => {
    const trace = normalizeUnderstandingTrace({
      version: "v1",
      populated: true,
      steps: [
        {
          phase: "claim_check",
          status: "pending",
          details: { duration_ms: 5, evidence_count: 1, confidence: 0.5 },
        },
      ],
    });
    expect(trace!.populated).toBe(true);
    expect(trace!.steps).toHaveLength(1);
    expect(trace!.steps[0].duration_ms).toBe(5);
    expect(trace!.steps[0].evidence_count).toBe(1);
    expect(trace!.steps[0].confidence).toBe(0.5);
    expect(understandingTraceHasSteps(trace!)).toBe(true);
  });

  it("chatResponseFromDiagnostics tolerates legacy payloads without understanding_trace", () => {
    const message: ChatMessage = {
      id: 1,
      session_id: "sess-1",
      role: "assistant",
      content: "Answer",
      request_id: "req-1",
      trace_id: null,
      used_context: true,
      cache_hit: false,
      cache_type: "none",
      sources: [],
      timing: { total_ms: 1, retrieval_ms: 1, generation_ms: 0, polish_ms: 0 },
      diagnostics: {
        request_id: "req-1",
        timing: { total_ms: 1, retrieval_ms: 1, generation_ms: 0, polish_ms: 0 },
        pipeline_stages: [],
      },
      created_at: null,
    };
    const response = chatResponseFromDiagnostics(message, message.diagnostics);
    expect(response).not.toBeNull();
    expect(response!.understanding_trace).toBeNull();
  });

  it("chatResponseFromDiagnostics parses understanding_trace when present", () => {
    const message: ChatMessage = {
      id: 2,
      session_id: "sess-1",
      role: "assistant",
      content: "Answer",
      request_id: "req-2",
      trace_id: null,
      used_context: true,
      cache_hit: false,
      cache_type: "none",
      sources: [],
      timing: { total_ms: 1, retrieval_ms: 1, generation_ms: 0, polish_ms: 0 },
      diagnostics: {
        request_id: "req-2",
        understanding_trace: EMPTY_STUB,
      },
      created_at: null,
    };
    const response = chatResponseFromDiagnostics(message, message.diagnostics);
    expect(response!.understanding_trace?.version).toBe("stub");
    expect(response!.understanding_trace?.steps).toEqual([]);
  });
});
