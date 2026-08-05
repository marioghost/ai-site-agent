import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getSettings } from "../../../api/client";
import { useChatSession } from "../../../context/ChatSessionContext";
import { useTranslation } from "../../../i18n";
import { Alert, Button, PageHeader, PageLayout, SectionCard, Toast } from "../../../ui";
import ChatDiagnosticsSidebar from "../../../components/chat/ChatDiagnosticsSidebar";

/**
 * S006 (G3-P2) — Engineering owner for Ask diagnostics.
 * Reuses the shared `ChatSessionContext` (mounted app-wide) so the currently
 * active Ask session's trace can be inspected here instead of on the product
 * `/ask` surface. If no session/turns exist yet, shows guidance to start a
 * conversation on Ask first.
 */
export default function EngAskDetailsScreen() {
  const { t } = useTranslation();
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

  const hasInspectableSession = Boolean(sessionId) && turns.length > 0 && activeTrace != null;

  return (
    <PageLayout>
      <PageHeader title={t("nav.eng_ask_details")} subtitle={t("eng.ask_details.subtitle")} />

      <Alert variant="info">{t("eng.ask_details.explainer")}</Alert>

      {!hasInspectableSession ? (
        <SectionCard title={t("eng.ask_details.empty_title")}>
          <p className="ds-help">{t("eng.ask_details.empty_body")}</p>
          <Link to="/ask">
            <Button variant="primary">{t("eng.ask_details.go_ask")}</Button>
          </Link>
        </SectionCard>
      ) : (
        <>
          <SectionCard
            title={t("eng.ask_details.session_title")}
            subtitle={sessionTitle || sessionId || undefined}
          >
            <Link to="/ask">
              <Button variant="secondary" size="sm">
                {t("eng.ask_details.go_ask")}
              </Button>
            </Link>
          </SectionCard>

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
        </>
      )}

      {toast && <Toast>{toast}</Toast>}
    </PageLayout>
  );
}
