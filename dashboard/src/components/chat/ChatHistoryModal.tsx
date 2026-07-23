import { useEffect, useMemo } from "react";
import { useChatSession } from "../../context/ChatSessionContext";
import { useTranslation } from "../../i18n";
import { Button, DataTable, Modal, type Column } from "../../ui";
import type { ChatSession } from "../../types";

export default function ChatHistoryModal() {
  const { t } = useTranslation();
  const {
    historyOpen,
    setHistoryOpen,
    historySessions,
    historyLoading,
    loadHistory,
    openSession,
    continueSession,
    sessionId,
  } = useChatSession();

  useEffect(() => {
    if (historyOpen) loadHistory();
  }, [historyOpen, loadHistory]);

  const columns = useMemo<Column<ChatSession>[]>(
    () => [
      {
        id: "title",
        header: t("chat.history.col.title"),
        cell: (s) => s.title || t("chat.history.untitled"),
      },
      {
        id: "created",
        header: t("chat.history.col.created_at"),
        cell: (s) =>
          s.created_at ? new Date(s.created_at).toLocaleString() : t("common.dash"),
      },
      {
        id: "last",
        header: t("chat.history.col.last_message"),
        cell: (s) =>
          s.last_message_at ? new Date(s.last_message_at).toLocaleString() : t("common.dash"),
      },
      {
        id: "count",
        header: t("chat.history.col.messages"),
        cell: (s) => s.message_count,
      },
      {
        id: "status",
        header: t("chat.history.col.status"),
        cell: (s) => t(`status.session.${s.status}`),
      },
      {
        id: "actions",
        header: t("chat.history.col.actions"),
        cell: (s) => (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button type="button" variant="secondary" size="sm" onClick={() => openSession(s.session_id)}>
              {t("chat.history.open")}
            </Button>
            {s.status === "active" && s.session_id !== sessionId && (
              <Button type="button" size="sm" onClick={() => continueSession(s.session_id)}>
                {t("chat.continue")}
              </Button>
            )}
          </div>
        ),
      },
    ],
    [continueSession, openSession, sessionId, t]
  );

  return (
    <Modal
      open={historyOpen}
      title={t("chat.history.title")}
      onClose={() => setHistoryOpen(false)}
      size="xl"
    >
      <DataTable
        columns={columns}
        data={historySessions}
        keyFn={(s) => s.session_id}
        loading={historyLoading}
        emptyTitle={t("chat.history.empty")}
      />
    </Modal>
  );
}
