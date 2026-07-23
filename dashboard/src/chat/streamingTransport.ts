import type { ChatStreamCallbacks } from "../lib/chatStreamParser";
import type { ChatResponse, ChatSource, TracePayload } from "../types";
import type { StreamEvent } from "./types";

export type StreamEventHandler = (event: StreamEvent) => void;

/** Maps SSE parser callbacks to normalized stream events for the reducer. */
export function createStreamEventBridge(onEvent: StreamEventHandler): ChatStreamCallbacks {
  return {
    onStart: (data) => {
      onEvent({
        type: "start",
        requestId: data.request_id,
        sessionId: data.session_id,
        messageId: data.message_id,
      });
    },
    onStatus: (data) => {
      onEvent({
        type: "pipeline.status",
        stage: data.stage,
        status: data.status,
        durationMs: data.duration_ms,
      });
    },
    onRetrieval: (data) => {
      onEvent({
        type: "retrieval",
        sources: (data.sources ?? []) as ChatSource[],
        retrievalDebug: data.retrieval_debug ?? null,
        tracePartial: (data.trace_partial as TracePayload | null) ?? null,
        usedContext: data.used_context,
        cacheHit: data.cache_hit,
        cacheType: data.cache_type,
      });
    },
    onDiagnostics: (data) => {
      onEvent({
        type: "diagnostics",
        promptDiagnostics: data.prompt_diagnostics ?? null,
        timingPartial: data.timing_partial ?? data.timing,
      });
    },
    onToken: (delta) => {
      onEvent({ type: "token", delta });
    },
    onPipelineStage: (data) => {
      onEvent({
        type: "pipeline.status",
        stage: data.stage,
        status: data.status,
        durationMs: data.duration_ms,
      });
    },
    onLlmFirstToken: (data) => {
      onEvent({ type: "llm.first_token", timeToFirstTokenMs: data.time_to_first_token_ms });
    },
    onFinal: (response: ChatResponse) => {
      onEvent({ type: "final", response });
    },
    onError: (message) => {
      onEvent({ type: "error", message });
    },
  };
}
