import { getHealth } from "../api/client";
import type { ChatTurn } from "../context/ChatSessionContext";
import type { ChatResponse, HealthResponse } from "../types";

export const CHAT_DIAGNOSTICS_EXPORT_VERSION = "1.0";

export interface ChatDiagnosticsExportInput {
  sessionId: string | null;
  sessionTitle: string;
  turns: ChatTurn[];
  response: ChatResponse;
  lastUserMessage: string;
}

export interface ChatDiagnosticsExportPayload {
  export_version: string;
  exported_at: string;
  environment: {
    dashboard_url: string;
    user_agent: string;
    language: string;
    timezone: string;
    online: boolean;
    viewport: { width: number; height: number };
  };
  session: {
    session_id: string | null;
    session_title: string;
    message_count: number;
  };
  conversation: {
    turns: ChatTurn[];
    last_user_message: string;
    last_assistant_answer: string;
  };
  response: ChatResponse;
  diagnostics: Record<string, unknown>;
  subsystem_health: HealthResponse | { error: string };
  summary: string;
}

function asLines(value: unknown): string {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(String).join(", ") : "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function section(title: string, lines: Array<[string, unknown]>): string {
  const body = lines
    .map(([label, value]) => `${label}: ${asLines(value)}`)
    .join("\n");
  return `${title}\n${"=".repeat(title.length)}\n${body}\n`;
}

function mergedRetrievalDebug(response: ChatResponse): Record<string, unknown> {
  return {
    ...(response.retrieval_debug ?? {}),
    ...(response.cache ? { cache: response.cache } : {}),
    ...(response.prompt_diagnostics ? { prompt_diagnostics: response.prompt_diagnostics } : {}),
    ...(response.error_type ? { error_type: response.error_type } : {}),
  };
}

function arrayLength(value: unknown): number | undefined {
  return Array.isArray(value) ? value.length : undefined;
}

function buildSummary(payload: ChatDiagnosticsExportPayload): string {
  const res = payload.response;
  const meta = res.metadata;
  const trace = res.trace;
  const cache = res.cache;
  const pd =
    res.prompt_diagnostics && typeof res.prompt_diagnostics === "object"
      ? (res.prompt_diagnostics as Record<string, unknown>)
      : null;
  const retrieval = mergedRetrievalDebug(res);

  const parts: string[] = [
    "AI Site Agent — Chat Test Diagnostics",
    `Exported: ${payload.exported_at}`,
    "",
    section("Question", [["User message", payload.conversation.last_user_message]]),
    section("Answer", [
      ["Text", res.answer],
      ["Used context", res.used_context],
      ["Cache hit", res.cache_hit],
      ["Cache type", res.cache_type],
      ["Error type", res.error_type ?? "—"],
    ]),
  ];

  if (res.timing) {
    parts.push(
      section("Timing (ms)", [
        ["Total", res.timing.total_ms],
        ["Retrieval", res.timing.retrieval_ms],
        ["Generation", res.timing.generation_ms],
        ["Polish", res.timing.polish_ms],
      ])
    );
  }

  if (cache) {
    parts.push(
      section("Cache", [
        ["Answer cache hit", cache.answer_cache_hit],
        ["Retrieval cache hit", cache.retrieval_cache_hit],
        ["Cache type", cache.cache_type],
        ["Cache key", cache.cache_key],
        ["Cache age (s)", cache.cache_age_seconds],
        ["TTL (s)", cache.cache_ttl_seconds],
        ["Cached chunks", cache.cached_selected_chunk_count],
        ["Cached context used", cache.cached_context_used],
        ["Negative cache", cache.negative_cache],
        ["Bypassed", cache.bypassed],
        ["Invalidation version", cache.invalidation_version],
      ])
    );
  }

  if (meta) {
    parts.push(
      section("Request metadata", [
        ["Request ID", meta.request_id],
        ["Session ID", meta.session_id],
        ["Knowledge version", meta.knowledge_version],
        ["Retrieval mode", meta.retrieval_mode],
        ["Query intent", meta.query_intent],
        ["User IP", meta.user_ip],
        ["User agent", meta.user_agent],
        ["Referrer", meta.referrer],
        ["Created at", meta.created_at],
      ])
    );
  }

  if (meta?.applied_knowledge_config) {
    const cfg = meta.applied_knowledge_config;
    parts.push(
      section("Applied knowledge profile", [
        ["Detected intent", cfg.detected_intent],
        ["Matched topic", cfg.matched_topic_label ?? cfg.matched_topic_key],
        ["Aliases", cfg.matched_aliases],
        ["Query expansions", cfg.query_expansions],
        ["Boosted document types", cfg.boosted_document_types],
        ["Deprioritized document types", cfg.deprioritized_document_types],
        ["Boosted content hints", cfg.boosted_content_hints],
        ["Supplemental queries", cfg.supplemental_queries],
      ])
    );
  }

  if (retrieval && Object.keys(retrieval).length > 0) {
    parts.push(
      section("Retrieval diagnostics", [
        ["Normalized query", retrieval.normalized_query],
        ["Variants", retrieval.variants],
        ["Mode", retrieval.mode],
        ["Similarity threshold", retrieval.similarity_threshold],
        ["Candidate count", retrieval.candidate_count ?? arrayLength(retrieval.dense)],
        ["Final chunk count", retrieval.final_chunk_count ?? arrayLength(retrieval.final)],
        ["Context length", retrieval.context_length],
        ["Prompt length", retrieval.prompt_length],
        ["No answer reason", retrieval.no_answer_reason],
        ["Query language", retrieval.query_language],
      ])
    );
    if (typeof retrieval.context_preview === "string" && retrieval.context_preview) {
      parts.push(`Context preview\n===============\n${retrieval.context_preview}\n`);
    }
  }

  if (pd) {
    parts.push(
      section("LLM generation", [
        ["Model", pd.model],
        ["Prompt chars", pd.prompt_chars],
        ["Context chars", pd.context_chars],
        ["num_ctx", pd.num_ctx],
        ["num_predict", pd.num_predict],
        ["Eval count", pd.eval_count],
        ["Done reason", pd.done_reason],
        ["Stop reason", pd.generation_stop_reason],
        ["Output truncated", pd.output_truncated],
        ["Polish enabled", pd.polish_enabled],
        ["Retry happened", pd.retry_happened],
        ["Generation ms", pd.generation_ms],
        ["Ollama request ms", pd.ollama_request_ms],
        ["Prompt build ms", pd.prompt_build_ms],
        ["Tokens/sec", pd.tokens_per_sec],
        ["LLM mode profile", pd.llm_mode_profile],
        ["Model warm", pd.model_warm],
        ["Keep alive", pd.keep_alive],
      ])
    );
  }

  if (trace?.steps?.length) {
    const pipeline = trace.steps
      .map(
        (step, index) =>
          `${index + 1}. ${step.name} [${step.status}] ${step.duration_ms}ms` +
          (Object.keys(step.details ?? {}).length
            ? ` — ${JSON.stringify(step.details)}`
            : "")
      )
      .join("\n");
    parts.push(`Search pipeline\n===============\n${pipeline}\n`);
  }

  if (trace?.retrieved_chunks?.length) {
    const chunks = trace.retrieved_chunks
      .map(
        (chunk, index) =>
          `${index + 1}. ${chunk.title || chunk.url} (${chunk.final_score.toFixed(3)})` +
          ` used=${chunk.used_in_context} type=${chunk.source_type}` +
          (chunk.text_preview ? `\n   ${chunk.text_preview.slice(0, 240)}` : "")
      )
      .join("\n");
    parts.push(`Retrieved chunks (${trace.retrieved_chunks.length})\n${"=".repeat(24)}\n${chunks}\n`);
  }

  if (res.sources?.length) {
    const sources = res.sources
      .map((s, i) => `${i + 1}. ${s.title || s.url} (${s.score.toFixed(3)}) — ${s.source_type}`)
      .join("\n");
    parts.push(`Answer sources\n==============\n${sources}\n`);
  }

  const health = payload.subsystem_health;
  if ("error" in health) {
    parts.push(section("Subsystem health", [["Status", `unavailable (${health.error})`]]));
  } else {
    parts.push(
      section("Subsystem health (at export time)", [
        ["App", `${health.app.status} — ${health.app.detail}`],
        ["Ollama", `${health.ollama.status} — ${health.ollama.detail}`],
        ["Qdrant", `${health.qdrant.status} — ${health.qdrant.detail}`],
        ["Database", `${health.database.status} — ${health.database.detail}`],
        ["DB revision", health.database.migration_version],
        ["DB pool", health.database.pool],
      ])
    );
  }

  parts.push(
    section("Session", [
      ["Session ID", payload.session.session_id],
      ["Title", payload.session.session_title],
      ["Messages in session", payload.session.message_count],
    ])
  );

  parts.push(
    section("Environment", [
      ["Dashboard URL", payload.environment.dashboard_url],
      ["Browser language", payload.environment.language],
      ["Timezone", payload.environment.timezone],
      ["Online", payload.environment.online],
    ])
  );

  return parts.join("\n");
}

async function fetchSubsystemHealth(): Promise<HealthResponse | { error: string }> {
  try {
    return await Promise.race([
      getHealth(),
      new Promise<never>((_, reject) => {
        window.setTimeout(() => reject(new Error("health check timeout")), 5000);
      }),
    ]);
  } catch (error) {
    const message = error instanceof Error ? error.message : "health check failed";
    return { error: message };
  }
}

function buildFilename(response: ChatResponse, exportedAt: string): string {
  const stamp = exportedAt.replace(/[:.]/g, "-").slice(0, 19);
  const id = response.request_id?.slice(0, 8) || response.session_id?.slice(0, 8) || "chat";
  return `chat-diagnostics-${id}-${stamp}.json`;
}

function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function buildChatDiagnosticsExport(
  input: ChatDiagnosticsExportInput
): Promise<ChatDiagnosticsExportPayload> {
  const exportedAt = new Date().toISOString();
  const lastAssistant = [...input.turns].reverse().find((turn) => turn.role === "assistant");

  const payload: ChatDiagnosticsExportPayload = {
    export_version: CHAT_DIAGNOSTICS_EXPORT_VERSION,
    exported_at: exportedAt,
    environment: {
      dashboard_url: window.location.href,
      user_agent: navigator.userAgent,
      language: navigator.language,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      online: navigator.onLine,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
    },
    session: {
      session_id: input.sessionId,
      session_title: input.sessionTitle,
      message_count: input.turns.length,
    },
    conversation: {
      turns: input.turns,
      last_user_message: input.lastUserMessage,
      last_assistant_answer: lastAssistant?.text ?? input.response.answer,
    },
    response: input.response,
    diagnostics: mergedRetrievalDebug(input.response),
    subsystem_health: await fetchSubsystemHealth(),
    summary: "",
  };

  payload.summary = buildSummary(payload);
  return payload;
}

export async function downloadChatDiagnosticsExport(
  input: ChatDiagnosticsExportInput
): Promise<string> {
  const payload = await buildChatDiagnosticsExport(input);
  const filename = buildFilename(input.response, payload.exported_at);
  downloadJson(filename, payload);
  return filename;
}
