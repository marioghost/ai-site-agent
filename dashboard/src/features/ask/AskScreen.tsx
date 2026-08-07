import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useChatSession } from "../../context/ChatSessionContext";
import { useTranslation } from "../../i18n";
import { LoadingState, PageHeader, PageLayout } from "../../ui";
import ChatToolbar from "../../components/chat/ChatToolbar";
import ChatMessageList from "../../components/chat/ChatMessageList";
import ChatComposer from "../../components/chat/ChatComposer";

/**
 * Ask is the product-only chat surface.
 * Engineering diagnostics live under Developer tools → Chat details.
 * History browsing lives under Insights → Activity.
 */
export default function AskScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    sessionTitle,
    turns,
    loading,
    initializing,
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

  if (initializing) {
    return (
      <PageLayout className="ds-chat-page ds-chat-page--product">
        <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />
        <LoadingState label={t("common.loading")} />
      </PageLayout>
    );
  }

  return (
    <PageLayout className="ds-chat-page ds-chat-page--product">
      <PageHeader title={t("nav.ask")} subtitle={t("ask.subtitle")} />

      <ChatToolbar
        sessionTitle={sessionTitle}
        loading={loading}
        onNewChat={onNewChat}
        onClearChat={onClearChat}
        onOpenHistory={() => navigate("/insights/activity")}
      />

      <div className="ds-chat-console ds-chat-console--single">
        <section className="ds-chat-main" aria-label={t("ask.conversation_label")}>
          <ChatMessageList turns={turns} loading={loading} density="product" />
          <ChatComposer value={input} onChange={setInput} onSend={onSend} loading={loading} />
        </section>
      </div>
    </PageLayout>
  );
}
