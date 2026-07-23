import type { CacheType, ChatMessage, ChatResponse, ChatTurn } from "../types";
import { turnIdFromMessage } from "../chat/messageRepository";
import { createEmptyDiagnostics } from "../chat/streamingReducer";
import type { AssistantDiagnostics } from "../chat/types";
import { normalizeUnderstandingTrace } from "./understandingTrace";

export function chatResponseFromDiagnostics(
  message: ChatMessage,
  diagnostics: Record<string, unknown> | null | undefined
): ChatResponse | null {
  if (!diagnostics || message.role !== "assistant" || Object.keys(diagnostics).length === 0) {
    return null;
  }
  const timingRaw = diagnostics.timing;
  const timing =
    timingRaw && typeof timingRaw === "object"
      ? (timingRaw as ChatResponse["timing"])
      : message.timing;

  return {
    session_id: message.session_id,
    request_id: message.request_id ?? String(diagnostics.request_id ?? ""),
    answer: message.content,
    sources: message.sources,
    used_context: message.used_context,
    cache_hit: message.cache_hit,
    cache_type: message.cache_type,
    timing,
    trace: (diagnostics.trace as ChatResponse["trace"]) ?? null,
    metadata: (diagnostics.metadata as ChatResponse["metadata"]) ?? null,
    retrieval_debug: (diagnostics.retrieval_debug as ChatResponse["retrieval_debug"]) ?? null,
    prompt_diagnostics:
      (diagnostics.prompt_diagnostics as ChatResponse["prompt_diagnostics"]) ??
      (diagnostics.retrieval_debug &&
      typeof diagnostics.retrieval_debug === "object" &&
      "prompt_diagnostics" in diagnostics.retrieval_debug
        ? ((diagnostics.retrieval_debug as Record<string, unknown>)
            .prompt_diagnostics as ChatResponse["prompt_diagnostics"])
        : null),
    cache: (diagnostics.cache as ChatResponse["cache"]) ?? null,
    error_type: (diagnostics.error_type as string | null) ?? null,
    understanding_trace:
      normalizeUnderstandingTrace(diagnostics.understanding_trace) ??
      normalizeUnderstandingTrace(
        (diagnostics as Record<string, unknown>).understandingTrace
      ),
  };
}

function diagnosticsFromPersistence(
  message: ChatMessage,
  response: ChatResponse | null,
  raw: Record<string, unknown> | null | undefined
): AssistantDiagnostics | undefined {
  if (message.role !== "assistant") return undefined;
  const requestId = message.request_id ?? String(raw?.request_id ?? "");
  const base = createEmptyDiagnostics(message.session_id, requestId);
  const pipelineRaw = raw?.pipeline_stages;
  const pipeline = Array.isArray(pipelineRaw)
    ? pipelineRaw.map((s, i) => {
        const row = s as Record<string, unknown>;
        return {
          id: String(row.stage ?? i),
          name: String(row.stage ?? `stage-${i}`),
          status: (row.status === "completed"
            ? "completed"
            : row.status === "running"
              ? "running"
              : row.status === "error"
                ? "error"
                : "pending") as AssistantDiagnostics["pipeline"][0]["status"],
          durationMs: row.duration_ms != null ? Number(row.duration_ms) : undefined,
        };
      })
    : base.pipeline;

  return {
    ...base,
    status: "completed",
    pipeline,
    sources: {
      status: message.sources.length > 0 ? "ready" : "empty",
      items: message.sources,
    },
    metrics: {
      usedContext: message.used_context,
      cacheHit: message.cache_hit,
      cacheType: message.cache_type as CacheType,
      timing: response?.timing ?? message.timing,
      firstTokenMs:
        response?.prompt_diagnostics &&
        typeof response.prompt_diagnostics === "object" &&
        "time_to_first_token_ms" in response.prompt_diagnostics
          ? Number((response.prompt_diagnostics as Record<string, unknown>).time_to_first_token_ms)
          : undefined,
    },
    retrievalDebug: (raw?.retrieval_debug as Record<string, unknown> | null) ?? null,
    promptDiagnostics: (raw?.prompt_diagnostics as Record<string, unknown> | null) ?? null,
    trace: (raw?.trace as AssistantDiagnostics["trace"]) ?? response?.trace ?? null,
    metadata: (raw?.metadata as AssistantDiagnostics["metadata"]) ?? response?.metadata ?? null,
    understandingTrace:
      normalizeUnderstandingTrace(raw?.understanding_trace) ??
      response?.understanding_trace ??
      null,
  };
}

export function messageToTurn(message: ChatMessage): ChatTurn {
  const id = turnIdFromMessage(message.id, message.role);
  if (message.role === "user") {
    return { id, role: "user", text: message.content, messageId: message.id };
  }
  const response = chatResponseFromDiagnostics(message, message.diagnostics);
  return {
    id,
    role: "assistant",
    text: message.content,
    messageId: message.id,
    status: "completed",
    sources: message.sources,
    usedContext: message.used_context,
    cacheHit: message.cache_hit,
    cacheType: message.cache_type as CacheType,
    timing: message.timing,
    trace: response?.trace ?? null,
    metadata: response?.metadata ?? null,
    response,
    diagnostics: diagnosticsFromPersistence(message, response, message.diagnostics),
  };
}

export function turnToChatResponse(turn: ChatTurn, sessionId: string): ChatResponse | null {
  if (turn.role !== "assistant") return null;
  if (turn.response) return turn.response;

  const timing = turn.timing ??
    turn.diagnostics?.metrics.timing ?? {
      total_ms: 0,
      retrieval_ms: 0,
      generation_ms: 0,
      polish_ms: 0,
    };

  if (!turn.text && !turn.diagnostics) return null;

  return {
    session_id: turn.diagnostics?.sessionId || sessionId,
    request_id: turn.diagnostics?.requestId ?? "",
    answer: turn.text,
    sources: turn.diagnostics?.sources.items ?? turn.sources ?? [],
    used_context: turn.diagnostics?.metrics.usedContext ?? turn.usedContext ?? false,
    cache_hit: turn.diagnostics?.metrics.cacheHit ?? turn.cacheHit ?? false,
    cache_type: turn.diagnostics?.metrics.cacheType ?? turn.cacheType ?? "none",
    timing: timing as ChatResponse["timing"],
    trace: turn.diagnostics?.trace ?? turn.trace ?? null,
    metadata: turn.diagnostics?.metadata ?? turn.metadata ?? null,
    retrieval_debug: (turn.diagnostics?.retrievalDebug as ChatResponse["retrieval_debug"]) ?? null,
    prompt_diagnostics: turn.diagnostics?.promptDiagnostics ?? null,
    cache: null,
    error_type: turn.diagnostics?.status === "error" ? "stream_error" : null,
    understanding_trace: turn.diagnostics?.understandingTrace ?? null,
  };
}
