import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useChatSession } from "../../context/ChatSessionContext";
import { useEngineeringMode } from "../../context/EngineeringModeContext";
import { useTranslation } from "../../i18n";
import { LoadingState, PageHeader, PageLayout } from "../../ui";
import ChatToolbar from "../../components/chat/ChatToolbar";
import ChatMessageList from "../../components/chat/ChatMessageList";
import ChatComposer from "../../components/chat/ChatComposer";
import AskDiagnosticsSlot from "./widgets/AskDiagnosticsSlot";

/**
 * Ask is the product chat surface.
 * With Engineering Mode on, diagnostics mount beside the conversation (click a reply to inspect).
 * History browsing lives under Insights → Activity.
 */
export default function AskScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { enabled: engineeringModeOn } = useEngineeringMode();
  const {
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

  const pageClass = engineeringModeOn
    ? "ds-chat-page"
    : "ds-chat-page ds-chat-page--product";

  const llmModel =
    engineeringModeOn &&
    activeTrace?.prompt_diagnostics &&
    typeof activeTrace.prompt_diagnostics === "object"
      ? String((activeTrace.prompt_diagnostics as Record<string, unknown>).model ?? "")
      : undefined;

  const lastUpdated =
    engineeringModeOn && activeTrace?.metadata?.created_at
      ? new Date(activeTrace.metadata.created_at).toLocaleString()
      : undefined;

  if (initializing) {
    return (
      <PageLayout className={pageClass}>
        <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />
        <LoadingState label={t("common.loading")} />
      </PageLayout>
    );
  }

  return (
    <PageLayout className={pageClass}>
      <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />

      <ChatToolbar
        sessionTitle={sessionTitle}
        loading={loading}
        lastUpdated={lastUpdated}
        onNewChat={onNewChat}
        onClearChat={onClearChat}
        onOpenHistory={() => navigate("/insights/activity")}
      />

      <div
        className={
          engineeringModeOn ? "ds-chat-console" : "ds-chat-console ds-chat-console--single"
        }
      >
        <section className="ds-chat-main" aria-label={t("ask.conversation_label")}>
          <ChatMessageList
            turns={turns}
            loading={loading}
            model={llmModel || undefined}
            selectedTurnIndex={engineeringModeOn ? selectedTurnIndex : null}
            activeAssistantId={engineeringModeOn ? activeAssistantId : null}
            onSelectAssistant={engineeringModeOn ? selectAssistantTurn : undefined}
            density={engineeringModeOn ? "engineering" : "product"}
          />
          <ChatComposer value={input} onChange={setInput} onSend={onSend} loading={loading} />
        </section>

        {engineeringModeOn ? <AskDiagnosticsSlot /> : null}
      </div>
    </PageLayout>
  );
}
