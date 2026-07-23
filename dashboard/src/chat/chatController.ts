import { sendChat, sendChatStream } from "../api/client";
import type { ChatTurn } from "../types";
import {
  mergeAssistantFromResponse,
  updateTurnById,
} from "./messageRepository";
import { reduceStreamEvent } from "./streamingReducer";
import { createStreamEventBridge } from "./streamingTransport";

export interface ChatExecutionCallbacks {
  onTurnsUpdate: (updater: (prev: ChatTurn[]) => ChatTurn[]) => void;
  onActiveAssistantId: (id: string | null) => void;
  onSessionId: (id: string) => void;
}

export interface ExecuteChatOptions {
  message: string;
  sessionId: string;
  assistantId: string;
  bypassCache?: boolean;
  signal?: AbortSignal;
  callbacks: ChatExecutionCallbacks;
}

function applyAssistantUpdate(
  callbacks: ChatExecutionCallbacks,
  assistantId: string,
  updater: (turn: ChatTurn) => ChatTurn
) {
  callbacks.onTurnsUpdate((prev) => updateTurnById(prev, assistantId, updater));
}

export async function executeChatRequest(options: ExecuteChatOptions): Promise<void> {
  const { message, sessionId, assistantId, bypassCache = false, signal, callbacks } = options;

  callbacks.onActiveAssistantId(assistantId);

  const handleEvent = (event: Parameters<typeof reduceStreamEvent>[1]) => {
    applyAssistantUpdate(callbacks, assistantId, (turn) => reduceStreamEvent(turn, event));
    if (event.type === "final") {
      callbacks.onSessionId(event.response.session_id);
    }
    if (event.type === "start") {
      callbacks.onSessionId(event.sessionId);
    }
  };

  try {
    const response = await sendChatStream(
      message,
      sessionId,
      createStreamEventBridge(handleEvent),
      bypassCache,
      true,
      signal
    );
    applyAssistantUpdate(callbacks, assistantId, (turn) => mergeAssistantFromResponse(turn, response));
    callbacks.onSessionId(response.session_id);
  } catch (streamErr) {
    if (signal?.aborted) {
      applyAssistantUpdate(callbacks, assistantId, (turn) => ({
        ...turn,
        status: "cancelled",
        diagnostics: turn.diagnostics
          ? { ...turn.diagnostics, status: "cancelled" }
          : turn.diagnostics,
      }));
      return;
    }
    try {
      const res = await sendChat(message, sessionId, true, bypassCache, true);
      applyAssistantUpdate(callbacks, assistantId, (turn) => mergeAssistantFromResponse(turn, res));
      callbacks.onSessionId(res.session_id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      const errMsg = err?.response?.data?.detail || "Chat request failed";
      applyAssistantUpdate(callbacks, assistantId, (turn) =>
        reduceStreamEvent(turn, { type: "error", message: errMsg })
      );
      throw e;
    }
  } finally {
    callbacks.onActiveAssistantId(null);
  }
}
