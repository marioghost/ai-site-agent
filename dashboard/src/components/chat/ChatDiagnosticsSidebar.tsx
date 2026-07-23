import { useState } from "react";
import { Download } from "lucide-react";
import { useTranslation } from "../../i18n";
import type { ChatTurn } from "../../types";
import type { PipelineStage } from "../../chat/types";
import { downloadChatDiagnosticsExport } from "../../lib/chatDiagnosticsExport";
import type { ChatResponse, RequestMetadata, TracePayload } from "../../types";
import { Button } from "../../ui";
import ChatSearchPipeline from "./ChatSearchPipeline";
import ChatProgressivePipeline from "./ChatProgressivePipeline";
import ChatRetrievalDiagnostics from "./ChatRetrievalDiagnostics";
import ChatAppliedConfig from "./ChatAppliedConfig";
import ChatRetrievedSources from "./ChatRetrievedSources";
import ChatQueryInfo from "./ChatQueryInfo";
import UnderstandingTracePanel from "./UnderstandingTracePanel";
import { DiagnosticSection, KvGrid, asList } from "./DiagnosticSection";
import { shouldShowUnderstandingTracePanel } from "../../lib/understandingTrace";
import type { UnderstandingTrace } from "../../types";

type Props = {
  sessionId: string | null;
  sessionTitle: string;
  turns: ChatTurn[];
  response: ChatResponse | null | undefined;
  meta: RequestMetadata | null | undefined;
  trace: TracePayload | null | undefined;
  pipelineStages?: PipelineStage[];
  retrievalDebug: Record<string, unknown>;
  lastUserMessage: string;
  semanticDiagnosticsV2Enabled?: boolean;
  chatDebugEnabled?: boolean;
  understandingTrace?: UnderstandingTrace | null;
  onRetryWithoutCache: (message: string) => void;
  onExportError?: (message: string) => void;
  onExportSuccess?: (filename: string) => void;
};

function ChatLlmGeneration({ debug }: { debug: Record<string, unknown> | null | undefined }) {
  const { t } = useTranslation();
  const pd = debug?.prompt_diagnostics;
  if (!pd || typeof pd !== "object") return null;
  const p = pd as Record<string, unknown>;

  return (
    <DiagnosticSection title={t("chat.llm_generation")} defaultOpen={false}>
      <KvGrid
        items={[
          { label: t("chat.model"), value: asList(p.model) },
          {
            label: "Prompt / context chars",
            value: `${String(p.prompt_chars ?? "—")} / ${String(p.context_chars ?? "—")}`,
          },
          {
            label: "num_ctx / num_predict",
            value: `${String(p.num_ctx ?? "—")} / ${String(p.num_predict ?? "—")}`,
          },
          {
            label: "Polish enabled",
            value: p.polish_enabled ? t("common.yes") : t("common.no"),
          },
          {
            label: "Retry",
            value: p.retry_happened ? t("common.yes") : t("common.no"),
          },
          { label: "Generation ms", value: String(p.generation_ms ?? "—") },
          { label: "Time to first token ms", value: String(p.time_to_first_token_ms ?? "—") },
          { label: "Connection ms", value: String(p.connection_ms ?? "—") },
          { label: "Load duration ms", value: String(p.load_duration_ms ?? "—") },
          { label: "Prompt eval ms", value: String(p.prompt_eval_duration_ms ?? "—") },
          { label: "Eval duration ms", value: String(p.eval_duration_ms ?? "—") },
          { label: "Ollama request ms", value: String(p.ollama_request_ms ?? "—") },
          { label: "Prompt build ms", value: String(p.prompt_build_ms ?? "—") },
          { label: "Tokens/sec", value: String(p.tokens_per_sec ?? p.tokens_per_second ?? "—") },
          { label: "LLM calls", value: String(p.llm_call_count ?? "—") },
          { label: "Mode", value: String(p.llm_mode_profile ?? "—") },
          {
            label: "Model warm",
            value: p.model_warm ? t("common.yes") : t("common.no"),
          },
          { label: "Model status", value: String(p.model_status ?? "—") },
          { label: "Bottleneck", value: String(p.performance_bottleneck ?? "—") },
          { label: "Keep alive", value: String(p.keep_alive ?? "—") },
          { label: "Streaming", value: p.streaming_enabled ? t("common.yes") : t("common.no") },
        ]}
      />
    </DiagnosticSection>
  );
}

export default function ChatDiagnosticsSidebar({
  sessionId,
  sessionTitle,
  turns,
  response,
  meta,
  trace,
  pipelineStages,
  retrievalDebug,
  lastUserMessage,
  semanticDiagnosticsV2Enabled = false,
  chatDebugEnabled = true,
  understandingTrace = null,
  onRetryWithoutCache,
  onExportError,
  onExportSuccess,
}: Props) {
  const { t } = useTranslation();
  const [exporting, setExporting] = useState(false);
  const hasPipeline =
    (trace && trace.steps.length > 0) ||
    Boolean(pipelineStages && pipelineStages.some((s) => s.status !== "pending"));
  const hasContent =
    hasPipeline ||
    meta ||
    Object.keys(retrievalDebug).length > 0 ||
    shouldShowUnderstandingTracePanel(
      semanticDiagnosticsV2Enabled,
      chatDebugEnabled,
      understandingTrace
    );

  const onExport = async () => {
    if (!response || exporting) return;
    setExporting(true);
    try {
      const filename = await downloadChatDiagnosticsExport({
        sessionId,
        sessionTitle,
        turns,
        response,
        lastUserMessage,
      });
      onExportSuccess?.(filename);
    } catch {
      onExportError?.(t("chat.export_diagnostics_error"));
    } finally {
      setExporting(false);
    }
  };

  if (!hasContent) {
    return (
      <aside className="ds-chat-diag">
        <div className="ds-chat-diag__empty">{t("trace.empty")}</div>
      </aside>
    );
  }

  return (
    <aside className="ds-chat-diag">
      <div className="ds-chat-diag__header">
        <div className="ds-chat-diag__header-copy">
          <h2 className="ds-chat-diag__title">{t("chat.diagnostics")}</h2>
          <p className="ds-chat-diag__hint">{t("chat.diagnostics_hint")}</p>
        </div>
        {response && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void onExport()}
            disabled={exporting}
            className="ds-chat-diag__export"
          >
            <Download size={14} aria-hidden />
            {exporting ? t("chat.export_diagnostics_busy") : t("chat.export_diagnostics")}
          </Button>
        )}
      </div>

      <div className="ds-chat-diag__viewport">
        <div className="ds-chat-diag__scroll">
          {trace && trace.steps.length > 0 ? (
            <ChatSearchPipeline trace={trace} />
          ) : pipelineStages && pipelineStages.length > 0 ? (
            <ChatProgressivePipeline stages={pipelineStages} />
          ) : null}

          {Object.keys(retrievalDebug).length > 0 && (
            <ChatRetrievalDiagnostics
              debug={retrievalDebug}
              lastUserMessage={lastUserMessage}
              onRetryWithoutCache={onRetryWithoutCache}
            />
          )}
          {meta?.applied_knowledge_config && (
            <ChatAppliedConfig config={meta.applied_knowledge_config} />
          )}
          {shouldShowUnderstandingTracePanel(
            semanticDiagnosticsV2Enabled,
            chatDebugEnabled,
            understandingTrace
          ) && <UnderstandingTracePanel trace={understandingTrace!} />}
          <ChatLlmGeneration debug={retrievalDebug} />
          {trace && trace.retrieved_chunks.length > 0 && (
            <ChatRetrievedSources chunks={trace.retrieved_chunks} />
          )}
          {meta && <ChatQueryInfo meta={meta} />}
        </div>
      </div>
    </aside>
  );
}
