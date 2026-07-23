import type { ChatResponse } from "../types";
import type { ChatTurn } from "../types";

const EMPTY_TIMING = {
  total_ms: 0,
  retrieval_ms: 0,
  generation_ms: 0,
  polish_ms: 0,
};

export function resolveActiveAssistantTurn(
  turns: ChatTurn[],
  selectedTurnIndex: number | null,
  activeAssistantId: string | null
): ChatTurn | null {
  if (activeAssistantId) {
    const active = turns.find((t) => t.id === activeAssistantId);
    if (active?.role === "assistant") return active;
  }
  if (selectedTurnIndex !== null) {
    const selected = turns[selectedTurnIndex];
    if (selected?.role === "assistant") return selected;
  }
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    if (turns[i]?.role === "assistant") return turns[i];
  }
  return null;
}

/** Build sidebar ChatResponse from structured turn data (streaming or completed). */
export function diagnosticsToChatResponse(turn: ChatTurn, sessionId: string): ChatResponse | null {
  if (turn.role !== "assistant") return null;
  if (turn.response) return turn.response;

  const d = turn.diagnostics;
  if (!d && !turn.text) return null;

  const timing = {
    ...EMPTY_TIMING,
    ...(d?.metrics.timing ?? turn.timing ?? {}),
  };

  return {
    session_id: d?.sessionId || sessionId,
    request_id: d?.requestId ?? "",
    answer: turn.text,
    sources: d?.sources.items ?? turn.sources ?? [],
    used_context: d?.metrics.usedContext ?? turn.usedContext ?? false,
    cache_hit: d?.metrics.cacheHit ?? turn.cacheHit ?? false,
    cache_type: d?.metrics.cacheType ?? turn.cacheType ?? "none",
    timing,
    trace: d?.trace ?? turn.trace ?? null,
    metadata: d?.metadata ?? turn.metadata ?? null,
    retrieval_debug: (d?.retrievalDebug as ChatResponse["retrieval_debug"]) ?? null,
    prompt_diagnostics: d?.promptDiagnostics ?? null,
    cache: null,
    error_type: d?.status === "error" ? "stream_error" : null,
    understanding_trace: d?.understandingTrace ?? null,
  };
}

export function pipelineStagesFromTraceOrDiagnostics(turn: ChatTurn) {
  const trace = turn.response?.trace ?? turn.diagnostics?.trace ?? turn.trace;
  if (trace?.steps?.length) return trace;
  const pipeline = turn.diagnostics?.pipeline ?? [];
  if (!pipeline.length) return null;
  return {
    request_id: turn.diagnostics?.requestId ?? "",
    steps: pipeline.map((s) => ({
      name: s.name,
      status: s.status === "running" ? "running" : s.status === "completed" ? "ok" : s.status,
      duration_ms: s.durationMs ?? 0,
      details: {},
    })),
  };
}
