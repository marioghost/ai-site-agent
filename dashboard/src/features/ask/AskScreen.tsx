import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useChatSession } from "../../context/ChatSessionContext";
import { useTranslation } from "../../i18n";
import { LoadingState, PageHeader, PageLayout } from "../../ui";
import ChatToolbar from "../../components/chat/ChatToolbar";
import ChatMessageList from "../../components/chat/ChatMessageList";
import ChatComposer from "../../components/chat/ChatComposer";

/**
 * S006 (G3-P2..P4) — Ask is the simple, product-only chat surface.
 * The engineering diagnostics panel moved to the Engineering Mode "Ask
 * details" screen; chat history browsing moved to Insights Activity. Ask
 * mounts only the core conversation chrome — progressive disclosure keeps
 * the product surface free of engineering/history chrome.
 */
export default function AskScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
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
  } = useChatSession();

  const [input, setInput] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !initializing) {
      setInput(q);
      searchParams.delete("q");
      setSearchParams(searchParams, { replace: true });
    }
  }, [initializing, searchParams, setSearchParams]);

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

  const meta = activeTrace?.metadata;
  const llmModel =
    activeTrace?.prompt_diagnostics && typeof activeTrace.prompt_diagnostics === "object"
      ? String((activeTrace.prompt_diagnostics as Record<string, unknown>).model ?? "")
      : undefined;

  const lastUpdated = meta?.created_at ? new Date(meta.created_at).toLocaleString() : null;

  if (initializing) {
    return (
      <PageLayout>
        <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />
        <LoadingState label={t("common.loading")} />
      </PageLayout>
    );
  }

  return (
    <PageLayout className="ds-chat-page">
      <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />

      <ChatToolbar
        sessionId={sessionId}
        sessionTitle={sessionTitle}
        loading={loading}
        lastUpdated={lastUpdated}
        onNewChat={onNewChat}
        onClearChat={onClearChat}
        onOpenHistory={() => navigate("/insights/activity")}
      />

      <div className="ds-chat-console ds-chat-console--single">
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
      </div>
    </PageLayout>
  );
}
