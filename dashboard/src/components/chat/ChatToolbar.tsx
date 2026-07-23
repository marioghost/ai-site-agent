import { Button } from "../../ui";
import { useTranslation } from "../../i18n";

type Props = {
  sessionId: string | null;
  sessionTitle: string;
  loading: boolean;
  lastUpdated?: string | null;
  onNewChat: () => void;
  onClearChat: () => void;
  onOpenHistory: () => void;
};

export default function ChatToolbar({
  sessionId,
  sessionTitle,
  loading,
  lastUpdated,
  onNewChat,
  onClearChat,
  onOpenHistory,
}: Props) {
  const { t } = useTranslation();

  return (
    <div className="ds-chat-toolbar">
      <div className="ds-chat-toolbar__actions">
        <Button type="button" onClick={onNewChat} disabled={loading}>
          {t("chat.new")}
        </Button>
        <Button type="button" variant="secondary" onClick={onClearChat} disabled={loading}>
          {t("chat.clear")}
        </Button>
        <Button type="button" variant="secondary" onClick={onOpenHistory}>
          {t("chat.history")}
        </Button>
      </div>
      {sessionId && (
        <div className="ds-chat-toolbar__meta">
          <span className="ds-chat-toolbar__session" title={sessionTitle || sessionId}>
            {sessionTitle || t("chat.history.untitled")} · {sessionId.slice(0, 8)}…
          </span>
          {lastUpdated && (
            <span className="ds-chat-toolbar__updated">
              {t("chat.last_updated")}: {lastUpdated}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
