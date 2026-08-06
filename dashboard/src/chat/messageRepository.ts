import type { ChatResponse, ChatTurn } from "../types";
import { finalStatusFromPromptDiagnostics } from "./generationStatus";
import { createEmptyDiagnostics } from "./streamingReducer";

export function newTurnId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* fall through */
    }
  }
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export function createUserTurn(text: string): ChatTurn {
  return { id: newTurnId(), role: "user", text };
}

export function createAssistantPlaceholder(sessionId: string, requestId: string): ChatTurn {
  return {
    id: newTurnId(),
    role: "assistant",
    text: "",
    status: "streaming",
    diagnostics: createEmptyDiagnostics(sessionId, requestId),
    sources: [],
  };
}

export function findTurnIndex(turns: ChatTurn[], turnId: string): number {
  return turns.findIndex((t) => t.id === turnId);
}

export function updateTurnById(
  turns: ChatTurn[],
  turnId: string,
  updater: (turn: ChatTurn) => ChatTurn
): ChatTurn[] {
  const idx = findTurnIndex(turns, turnId);
  if (idx < 0) return turns;
  const next = [...turns];
  next[idx] = updater(next[idx]);
  return next;
}

export function mergeAssistantFromResponse(turn: ChatTurn, response: ChatResponse): ChatTurn {
  const diag = turn.diagnostics;
  const pd =
    response.prompt_diagnostics && typeof response.prompt_diagnostics === "object"
      ? (response.prompt_diagnostics as Record<string, unknown>)
      : null;
  const finalStatus = finalStatusFromPromptDiagnostics(pd, {
    errorType: response.error_type,
  });
  return {
    ...turn,
    text: response.answer,
    status: finalStatus,
    sources: response.sources,
    usedContext: response.used_context,
    cacheHit: response.cache_hit,
    cacheType: response.cache_type,
    timing: response.timing,
    trace: response.trace,
    metadata: response.metadata,
    response,
    diagnostics: diag
      ? {
          ...diag,
          status: finalStatus,
          sessionId: response.session_id,
          requestId: response.request_id,
          sources: {
            status: response.sources.length > 0 ? "ready" : "empty",
            items: response.sources,
          },
          metrics: {
            ...diag.metrics,
            usedContext: response.used_context,
            cacheHit: response.cache_hit,
            cacheType: response.cache_type,
            timing: response.timing,
            firstTokenMs:
              diag.metrics.firstTokenMs ??
              (pd && "time_to_first_token_ms" in pd
                ? Number(pd.time_to_first_token_ms)
                : undefined),
          },
          retrievalDebug:
            (response.retrieval_debug as Record<string, unknown> | null) ?? diag.retrievalDebug,
          promptDiagnostics: response.prompt_diagnostics ?? diag.promptDiagnostics,
          trace: response.trace ?? diag.trace,
          metadata: response.metadata ?? diag.metadata,
          understandingTrace: response.understanding_trace ?? diag.understandingTrace,
        }
      : undefined,
  };
}

export function turnIdFromMessage(messageId: number, role: string): string {
  return `${role}-${messageId}`;
}
