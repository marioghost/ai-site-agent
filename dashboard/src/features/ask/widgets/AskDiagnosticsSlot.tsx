import ChatDiagnosticsSidebar from "../../../components/chat/ChatDiagnosticsSidebar";
import { useTranslation } from "../../../i18n";
import { Toast } from "../../../ui";
import { useAskDiagnosticsView } from "../useAskDiagnosticsView";

/**
 * Engineering Mode slot: answer diagnostics beside Ask (RFC-102 progressive disclosure).
 * Click an assistant reply in the chat list to inspect that turn.
 */
export default function AskDiagnosticsSlot() {
  const { t } = useTranslation();
  const {
    sessionId,
    sessionTitle,
    turns,
    activeTrace,
    pipelineStages,
    trace,
    meta,
    retrievalDebug,
    lastUserMessage,
    semanticDiagnosticsV2Enabled,
    chatDebugEnabled,
    toast,
    setToast,
    sendMessage,
  } = useAskDiagnosticsView();

  return (
    <>
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
        onExportSuccess={(filename) => setToast(t("chat.export_diagnostics_done", { filename }))}
        onExportError={setToast}
      />
      {toast ? <Toast>{toast}</Toast> : null}
    </>
  );
}
