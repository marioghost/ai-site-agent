import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getSettings } from "../api/client";
import { useChatSession } from "../context/ChatSessionContext";
import { useTranslation } from "../i18n";
import { LoadingState, PageHeader, PageLayout, Toast } from "../ui";
import ChatToolbar from "../components/chat/ChatToolbar";
import ChatMessageList from "../components/chat/ChatMessageList";
import ChatComposer from "../components/chat/ChatComposer";
import ChatDiagnosticsSidebar from "../components/chat/ChatDiagnosticsSidebar";
import ChatHistoryModal from "../components/chat/ChatHistoryModal";

export default function ChatTestPage() {
  const { t } = useTranslation();
  const {
    sessionId,
    sessionTitle,
    turns,
    loading,
    initializing,
    activeTrace,
    selectedTurnIndex,
    activeAssistantId,
    selectAssistantTurn,
    sendMessage,
    startNewChat,
    clearChat,
    setHistoryOpen,
  } = useChatSession();

  const [input, setInput] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [semanticDiagnosticsV2Enabled, setSemanticDiagnosticsV2Enabled] = useState(false);
  const [chatDebugEnabled, setChatDebugEnabled] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !initializing) {
      setInput(q);
      searchParams.delete("q");
      setSearchParams(searchParams, { replace: true });
    }
  }, [initializing, searchParams, setSearchParams]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2500);
    return () => window.clearTimeout(timer);
  }, [toast]);

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

  const onSend = async () => {
    const message = input.trim();
    if (!message || loading) return;
    await sendMessage(message);
    setInput("");
  };

  const onNewChat = async () => {
    if (turns.length > 0 && !window.confirm(t("chat.confirm_new"))) return;
    await startNewChat();
  };

  const onClearChat = async () => {
    if (!window.confirm(t("chat.confirm_clear"))) return;
    await clearChat();
  };

  const activeTurn = useMemo(() => {
    if (activeAssistantId) {
      const t = turns.find((x) => x.id === activeAssistantId);
      if (t?.role === "assistant") return t;
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

  const lastUpdated = meta?.created_at
    ? new Date(meta.created_at).toLocaleString()
    : null;

  if (initializing) {
    return (
      <PageLayout>
        <PageHeader title={t("chat.title")} subtitle={t("chat.subtitle")} />
        <LoadingState label={t("common.loading")} />
      </PageLayout>
    );
  }

  return (
    <PageLayout className="ds-chat-page">
      <PageHeader title={t("chat.title")} subtitle={t("chat.subtitle")} />

      <ChatToolbar
        sessionId={sessionId}
        sessionTitle={sessionTitle}
        loading={loading}
        lastUpdated={lastUpdated}
        onNewChat={onNewChat}
        onClearChat={onClearChat}
        onOpenHistory={() => setHistoryOpen(true)}
      />

      <div className="ds-chat-console">
        <section className="ds-chat-main">
          <ChatMessageList
            turns={turns}
            loading={loading}
            model={llmModel || undefined}
            selectedTurnIndex={selectedTurnIndex}
            activeAssistantId={activeAssistantId}
            onSelectAssistant={selectAssistantTurn}
          />
          <ChatComposer value={input} onChange={setInput} onSend={onSend} loading={loading} />
        </section>

        <ChatDiagnosticsSidebar
          sessionId={sessionId}
          sessionTitle={sessionTitle}
          turns={turns}
          response={activeTrace}
          meta={meta}
          trace={trace}
          pipelineStages={pipelineStages}
          retrievalDebug={retrievalDebug}
          semanticDiagnosticsV2Enabled={semanticDiagnosticsV2Enabled}
          chatDebugEnabled={chatDebugEnabled}
          understandingTrace={activeTrace?.understanding_trace ?? null}
          lastUserMessage={lastUserMessage}
          onRetryWithoutCache={(message) => sendMessage(message, { bypassCache: true })}
          onExportSuccess={(filename) =>
            setToast(t("chat.export_diagnostics_done", { filename }))
          }
          onExportError={setToast}
        />
      </div>

      {toast && <Toast>{toast}</Toast>}
      <ChatHistoryModal />
    </PageLayout>
  );
}
