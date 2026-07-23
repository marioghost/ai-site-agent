import type { ChatResponse, ChatSource, TimingMetrics } from "../types";

export interface ChatStreamCallbacks {
  onStart?: (data: {
    request_id: string;
    session_id: string;
    message_id?: string;
    streaming?: boolean;
  }) => void;
  onStatus?: (data: { stage: string; status: string; duration_ms?: number }) => void;
  onPipelineStage?: (data: { stage: string; status: string; duration_ms?: number }) => void;
  onRetrieval?: (data: {
    sources: ChatSource[];
    retrieval_debug?: Record<string, unknown> | null;
    trace_partial?: unknown;
    used_context?: boolean;
    cache_hit?: boolean;
    cache_type?: string;
  }) => void;
  onToken?: (delta: string) => void;
  onDiagnostics?: (data: {
    prompt_diagnostics?: Record<string, unknown> | null;
    timing_partial?: Partial<TimingMetrics>;
    timing?: Partial<TimingMetrics>;
  }) => void;
  onLlmFirstToken?: (data: { time_to_first_token_ms: number }) => void;
  onFinal?: (response: ChatResponse) => void;
  onError?: (message: string) => void;
}

export interface ParseChatStreamState {
  currentEvent: string;
  finalResponse: ChatResponse | null;
}

export function createChatStreamState(): ParseChatStreamState {
  return { currentEvent: "message", finalResponse: null };
}

function unwrapFinalResponse(data: Record<string, unknown>): ChatResponse {
  const raw = (data.response ?? data) as ChatResponse;
  return raw;
}

function tokenDelta(data: Record<string, unknown>): string {
  if (typeof data.delta === "string") return data.delta;
  if (typeof data.text === "string") return data.text;
  return "";
}

function emitPipelineStatus(
  callbacks: ChatStreamCallbacks,
  data: { stage: string; status: string; duration_ms?: number }
) {
  callbacks.onStatus?.(data);
  callbacks.onPipelineStage?.(data);
}

export function processChatStreamLine(
  line: string,
  state: ParseChatStreamState,
  callbacks: ChatStreamCallbacks
): void {
  if (line.startsWith("event:")) {
    state.currentEvent = line.slice(6).trim();
    return;
  }
  if (!line.startsWith("data:")) return;

  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return;

  const data = JSON.parse(payload) as Record<string, unknown>;
  switch (state.currentEvent) {
    case "start":
      callbacks.onStart?.(
        data as {
          request_id: string;
          session_id: string;
          message_id?: string;
          streaming?: boolean;
        }
      );
      break;
    case "status":
    case "pipeline.stage":
      emitPipelineStatus(
        callbacks,
        data as { stage: string; status: string; duration_ms?: number }
      );
      break;
    case "retrieval":
    case "sources.completed":
      callbacks.onRetrieval?.(
        data as NonNullable<ChatStreamCallbacks["onRetrieval"]> extends (d: infer D) => void
          ? D
          : never
      );
      break;
    case "token":
      callbacks.onToken?.(tokenDelta(data));
      break;
    case "llm.first_token":
      callbacks.onLlmFirstToken?.({
        time_to_first_token_ms: Number(data.time_to_first_token_ms ?? 0),
      });
      break;
    case "diagnostics": {
      const timingPartial =
        (data.timing_partial as Partial<TimingMetrics> | undefined) ??
        (data.timing as Partial<TimingMetrics> | undefined);
      callbacks.onDiagnostics?.({
        prompt_diagnostics: data.prompt_diagnostics as Record<string, unknown> | null,
        timing_partial: timingPartial,
        timing: timingPartial,
      });
      break;
    }
    case "final":
    case "response.completed": {
      const response = unwrapFinalResponse(data);
      state.finalResponse = response;
      callbacks.onFinal?.(response);
      break;
    }
    case "error": {
      const message = String(data.message ?? data.error_type ?? "stream error");
      callbacks.onError?.(message);
      throw new Error(message);
    }
    default:
      break;
  }
}

export function parseChatStreamChunk(
  chunk: string,
  buffer: string,
  state: ParseChatStreamState,
  callbacks: ChatStreamCallbacks
): string {
  const combined = buffer + chunk;
  const lines = combined.split("\n");
  const remainder = lines.pop() || "";
  for (const line of lines) {
    processChatStreamLine(line, state, callbacks);
  }
  return remainder;
}
