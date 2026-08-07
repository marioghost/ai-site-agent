/**
 * Derived Ask diagnostics view from the shared chat session.
 * Used when Engineering Mode mounts the diagnostics slot beside Ask.
 */
import { useEffect, useMemo, useState } from "react";
import { getSettings } from "../../api/client";
import { useChatSession } from "../../context/ChatSessionContext";

export function useAskDiagnosticsView() {
  const {
    sessionId,
    sessionTitle,
    turns,
    activeTrace,
    selectedTurnIndex,
    activeAssistantId,
    sendMessage,
  } = useChatSession();

  const [toast, setToast] = useState<string | null>(null);
  const [semanticDiagnosticsV2Enabled, setSemanticDiagnosticsV2Enabled] = useState(false);
  const [chatDebugEnabled, setChatDebugEnabled] = useState(true);

  useEffect(() => {
    getSettings()
      .then((settings) => {
        setSemanticDiagnosticsV2Enabled(settings.enable_semantic_diagnostics_v2 ?? false);
        setChatDebugEnabled(settings.enable_chat_debug_payload ?? true);
      })
      .catch(() => {
        setSemanticDiagnosticsV2Enabled(false);
        setChatDebugEnabled(true);
      });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const activeTurn = useMemo(() => {
    if (activeAssistantId) {
      const turn = turns.find((x) => x.id === activeAssistantId);
      if (turn?.role === "assistant") return turn;
    }
    if (selectedTurnIndex != null && turns[selectedTurnIndex]?.role === "assistant") {
      return turns[selectedTurnIndex];
    }
    return [...turns].reverse().find((x) => x.role === "assistant") ?? null;
  }, [turns, selectedTurnIndex, activeAssistantId]);

  const pipelineStages = activeTurn?.diagnostics?.pipeline ?? [];
  const trace = activeTrace?.trace;
  const meta = activeTrace?.metadata;
  const retrievalDebug = useMemo(() => {
    if (!activeTrace) return {} as Record<string, unknown>;
    const fromRetrieval =
      activeTrace.retrieval_debug && typeof activeTrace.retrieval_debug === "object"
        ? activeTrace.retrieval_debug
        : {};
    return {
      ...fromRetrieval,
      ...(activeTrace.cache ? { cache: activeTrace.cache } : {}),
      ...(activeTrace.prompt_diagnostics
        ? { prompt_diagnostics: activeTrace.prompt_diagnostics }
        : {}),
      ...(activeTrace.error_type ? { error_type: activeTrace.error_type } : {}),
    } as Record<string, unknown>;
  }, [activeTrace]);

  const lastUserMessage = useMemo(() => {
    if (selectedTurnIndex == null) {
      return [...turns].reverse().find((turn) => turn.role === "user")?.text ?? "";
    }
    for (let i = selectedTurnIndex; i >= 0; i -= 1) {
      if (turns[i]?.role === "user") return turns[i].text;
    }
    return "";
  }, [selectedTurnIndex, turns]);

  const llmModel =
    activeTrace?.prompt_diagnostics && typeof activeTrace.prompt_diagnostics === "object"
      ? String((activeTrace.prompt_diagnostics as Record<string, unknown>).model ?? "")
      : undefined;

  return {
    sessionId,
    sessionTitle,
    turns,
    activeTrace,
    pipelineStages,
    trace,
    meta,
    retrievalDebug,
    lastUserMessage,
    llmModel,
    semanticDiagnosticsV2Enabled,
    chatDebugEnabled,
    toast,
    setToast,
    sendMessage,
  };
}
