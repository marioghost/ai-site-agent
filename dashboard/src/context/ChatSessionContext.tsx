import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { flushSync } from "react-dom";
import {
  clearChatSession,
  createChatSession,
  getChatSession,
  listChatSessions,
} from "../api/client";
import { executeChatRequest } from "../chat/chatController";
import { createAssistantPlaceholder, createUserTurn } from "../chat/messageRepository";
import { diagnosticsToChatResponse } from "../chat/diagnosticsView";
import type { ChatTurn } from "../types";
import { messageToTurn } from "../lib/chatTurnDiagnostics";
import type { ChatMessage, ChatResponse, ChatSession, ChatSessionDetail } from "../types";

export const ACTIVE_SESSION_STORAGE_KEY = "ai_agent_active_chat_session_id";

export type { ChatTurn } from "../types";

interface ChatSessionContextValue {
  sessionId: string | null;
  sessionTitle: string;
  turns: ChatTurn[];
  loading: boolean;
  initializing: boolean;
  activeTrace: ChatResponse | null;
  selectedTurnIndex: number | null;
  activeAssistantId: string | null;
  historyOpen: boolean;
  historySessions: ChatSession[];
  historyLoading: boolean;
  setHistoryOpen: (open: boolean) => void;
  selectAssistantTurn: (index: number) => void;
  sendMessage: (message: string, options?: { bypassCache?: boolean }) => Promise<void>;
  stopGeneration: () => void;
  startNewChat: () => Promise<void>;
  clearChat: () => Promise<void>;
  loadHistory: () => Promise<void>;
  openSession: (sessionId: string) => Promise<void>;
  continueSession: (sessionId: string) => Promise<void>;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

function persistSessionId(id: string | null) {
  try {
    if (id) localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, id);
    else localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function readStoredSessionId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function messagesToTurns(messages: ChatMessage[]): ChatTurn[] {
  return messages.map(messageToTurn);
}

function applySessionDetail(
  detail: ChatSessionDetail,
  setSessionId: (id: string) => void,
  setSessionTitle: (t: string) => void,
  setTurns: (t: ChatTurn[]) => void,
  setSelectedTurnIndex: (v: number | null) => void
) {
  const nextTurns = messagesToTurns(detail.messages);
  setSessionId(detail.session_id);
  setSessionTitle(detail.title || "");
  setTurns(nextTurns);
  const lastAssistant = [...nextTurns]
    .map((turn, index) => ({ turn, index }))
    .reverse()
    .find(({ turn }) => turn.role === "assistant");
  setSelectedTurnIndex(lastAssistant?.index ?? null);
  persistSessionId(detail.session_id);
}

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [selectedTurnIndex, setSelectedTurnIndex] = useState<number | null>(null);
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySessions, setHistorySessions] = useState<ChatSession[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const initStarted = useRef(false);
  const streamAbortRef = useRef<AbortController | null>(null);

  const activeTrace = useMemo(() => {
    if (!sessionId) return null;
    const active =
      activeAssistantId != null
        ? turns.find((t) => t.id === activeAssistantId)
        : selectedTurnIndex != null
          ? turns[selectedTurnIndex]
          : null;
    const turn =
      active?.role === "assistant"
        ? active
        : [...turns].reverse().find((t) => t.role === "assistant") ?? null;
    if (!turn || turn.role !== "assistant") return null;
    return diagnosticsToChatResponse(turn, sessionId);
  }, [sessionId, turns, selectedTurnIndex, activeAssistantId]);

  const ensureSession = useCallback(async (): Promise<ChatSessionDetail> => {
    const stored = readStoredSessionId();
    if (stored) {
      try {
        return await getChatSession(stored);
      } catch {
        /* fall through */
      }
    }
    const created = await createChatSession(null);
    persistSessionId(created.session_id);
    return created;
  }, []);

  useEffect(() => {
    if (initStarted.current) return;
    initStarted.current = true;
    let cancelled = false;
    (async () => {
      try {
        const detail = await ensureSession();
        if (cancelled) return;
        applySessionDetail(
          detail,
          setSessionId,
          setSessionTitle,
          setTurns,
          setSelectedTurnIndex
        );
      } finally {
        if (!cancelled) setInitializing(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ensureSession]);

  const selectAssistantTurn = useCallback((index: number) => {
    const turn = turns[index];
    if (!turn || turn.role !== "assistant") return;
    setSelectedTurnIndex(index);
  }, [turns]);

  const stopGeneration = useCallback(() => {
    streamAbortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (message: string, options?: { bypassCache?: boolean }) => {
      if (!message.trim() || loading) return;
      let sid = sessionId;
      if (!sid) {
        const detail = await ensureSession();
        sid = detail.session_id;
        setSessionId(sid);
        persistSessionId(sid);
      }

      const userTurn = createUserTurn(message);
      const assistantTurn = createAssistantPlaceholder(sid, "");
      const assistantId = assistantTurn.id;

      flushSync(() => {
        setTurns((prev) => {
          const next = [...prev, userTurn, assistantTurn];
          setSelectedTurnIndex(next.length - 1);
          return next;
        });
      });

      setLoading(true);
      streamAbortRef.current?.abort();
      const abortController = new AbortController();
      streamAbortRef.current = abortController;

      try {
        await executeChatRequest({
          message,
          sessionId: sid,
          assistantId,
          bypassCache: options?.bypassCache ?? false,
          signal: abortController.signal,
          callbacks: {
            onTurnsUpdate: (updater) => setTurns(updater),
            onActiveAssistantId: setActiveAssistantId,
            onSessionId: (id) => {
              setSessionId(id);
              persistSessionId(id);
            },
          },
        });
      } catch {
        /* error applied to assistant turn */
      } finally {
        setLoading(false);
        streamAbortRef.current = null;
      }
    },
    [ensureSession, loading, sessionId]
  );

  const startNewChat = useCallback(async () => {
    const detail = await createChatSession(sessionId);
    applySessionDetail(
      detail,
      setSessionId,
      setSessionTitle,
      setTurns,
      setSelectedTurnIndex
    );
    setActiveAssistantId(null);
  }, [sessionId]);

  const clearChat = useCallback(async () => {
    if (!sessionId) return;
    const detail = await clearChatSession(sessionId);
    applySessionDetail(
      detail,
      setSessionId,
      setSessionTitle,
      setTurns,
      setSelectedTurnIndex
    );
    setActiveAssistantId(null);
  }, [sessionId]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await listChatSessions(1, 50);
      setHistorySessions(res.items);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const openSession = useCallback(async (id: string) => {
    const detail = await getChatSession(id);
    applySessionDetail(
      detail,
      setSessionId,
      setSessionTitle,
      setTurns,
      setSelectedTurnIndex
    );
    setActiveAssistantId(null);
    setHistoryOpen(false);
  }, []);

  const continueSession = useCallback(
    async (id: string) => {
      await openSession(id);
    },
    [openSession]
  );

  const value = useMemo<ChatSessionContextValue>(
    () => ({
      sessionId,
      sessionTitle,
      turns,
      loading,
      initializing,
      activeTrace,
      selectedTurnIndex,
      activeAssistantId,
      historyOpen,
      historySessions,
      historyLoading,
      setHistoryOpen,
      selectAssistantTurn,
      sendMessage,
      stopGeneration,
      startNewChat,
      clearChat,
      loadHistory,
      openSession,
      continueSession,
    }),
    [
      sessionId,
      sessionTitle,
      turns,
      loading,
      initializing,
      activeTrace,
      selectedTurnIndex,
      activeAssistantId,
      historyOpen,
      historySessions,
      historyLoading,
      selectAssistantTurn,
      sendMessage,
      stopGeneration,
      startNewChat,
      clearChat,
      loadHistory,
      openSession,
      continueSession,
    ]
  );

  return (
    <ChatSessionContext.Provider value={value}>
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSession() {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) {
    throw new Error("useChatSession must be used within ChatSessionProvider");
  }
  return ctx;
}
