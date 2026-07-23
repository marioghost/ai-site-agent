import type { CacheType, ChatResponse, TimingMetrics } from "../types";
import type { ChatTurn } from "../types";
import type {
  AssistantDiagnostics,
  PipelineStage,
  PipelineStageStatus,
  StreamEvent,
} from "./types";

const PIPELINE_ORDER = [
  "receive_request",
  "intent_detection",
  "query_expansion",
  "retrieval",
  "reranking",
  "context_building",
  "prompt_generation",
  "generation",
  "post_processing",
] as const;

function defaultPipeline(): PipelineStage[] {
  return PIPELINE_ORDER.map((name) => ({
    id: name,
    name,
    status: "pending" as PipelineStageStatus,
  }));
}

export function createEmptyDiagnostics(sessionId: string, requestId: string): AssistantDiagnostics {
  return {
    requestId,
    sessionId,
    status: "streaming",
    pipeline: defaultPipeline(),
    sources: { status: "loading", items: [] },
    metrics: { timing: {} },
    retrievalDebug: null,
    promptDiagnostics: null,
    trace: null,
    metadata: null,
    understandingTrace: null,
  };
}

function mapBackendStatus(status: string): PipelineStageStatus {
  if (status === "running") return "running";
  if (status === "completed") return "completed";
  if (status === "error") return "error";
  if (status === "skipped") return "skipped";
  return "pending";
}

function upsertPipelineStage(
  pipeline: PipelineStage[],
  stage: string,
  status: PipelineStageStatus,
  durationMs?: number
): PipelineStage[] {
  const idx = pipeline.findIndex((s) => s.name === stage);
  if (idx >= 0) {
    const next = [...pipeline];
    next[idx] = { ...next[idx], status, durationMs: durationMs ?? next[idx].durationMs };
    return next;
  }
  return [...pipeline, { id: stage, name: stage, status, durationMs }];
}

function markReceiveComplete(pipeline: PipelineStage[]): PipelineStage[] {
  return upsertPipelineStage(pipeline, "receive_request", "completed");
}

export function reduceStreamEvent(turn: ChatTurn, event: StreamEvent): ChatTurn {
  if (turn.role !== "assistant") return turn;

  const baseDiag = turn.diagnostics ?? createEmptyDiagnostics("", "");

  switch (event.type) {
    case "start": {
      const diagnostics: AssistantDiagnostics = {
        ...createEmptyDiagnostics(event.sessionId, event.requestId),
        pipeline: markReceiveComplete(defaultPipeline()),
      };
      return { ...turn, status: "streaming", diagnostics };
    }
    case "pipeline.status": {
      const pipeline = upsertPipelineStage(
        baseDiag.pipeline,
        event.stage,
        mapBackendStatus(event.status),
        event.durationMs
      );
      return {
        ...turn,
        diagnostics: { ...baseDiag, pipeline },
      };
    }
    case "retrieval": {
      const sources = event.sources ?? [];
      const pipeline = upsertPipelineStage(baseDiag.pipeline, "retrieval", "completed");
      return {
        ...turn,
        sources,
        usedContext: event.usedContext,
        cacheHit: event.cacheHit,
        cacheType: (event.cacheType as CacheType) ?? turn.cacheType,
        trace: event.tracePartial ?? turn.trace,
        diagnostics: {
          ...baseDiag,
          pipeline,
          sources: {
            status: sources.length > 0 ? "ready" : "empty",
            items: sources,
          },
          metrics: {
            ...baseDiag.metrics,
            usedContext: event.usedContext,
            cacheHit: event.cacheHit,
            cacheType: (event.cacheType as CacheType) ?? baseDiag.metrics.cacheType,
          },
          retrievalDebug: event.retrievalDebug ?? baseDiag.retrievalDebug,
          trace: event.tracePartial ?? baseDiag.trace,
        },
      };
    }
    case "diagnostics": {
      const timing = {
        ...baseDiag.metrics.timing,
        ...(event.timingPartial ?? {}),
      } as Partial<TimingMetrics>;
      return {
        ...turn,
        diagnostics: {
          ...baseDiag,
          promptDiagnostics: event.promptDiagnostics ?? baseDiag.promptDiagnostics,
          metrics: { ...baseDiag.metrics, timing },
        },
      };
    }
    case "token":
      return {
        ...turn,
        text: (turn.text || "") + event.delta,
        diagnostics: {
          ...baseDiag,
          pipeline: upsertPipelineStage(baseDiag.pipeline, "generation", "running"),
        },
      };
    case "llm.first_token":
      return {
        ...turn,
        diagnostics: {
          ...baseDiag,
          metrics: { ...baseDiag.metrics, firstTokenMs: event.timeToFirstTokenMs },
        },
      };
    case "final": {
      const res = event.response;
      return {
        ...turn,
        text: res.answer,
        status: "completed",
        sources: res.sources,
        usedContext: res.used_context,
        cacheHit: res.cache_hit,
        cacheType: res.cache_type,
        timing: res.timing,
        trace: res.trace,
        metadata: res.metadata,
        response: res,
        diagnostics: {
          ...baseDiag,
          status: "completed",
          sessionId: res.session_id,
          requestId: res.request_id,
          pipeline: baseDiag.pipeline.map((s) =>
            s.status === "running" ? { ...s, status: "completed" as PipelineStageStatus } : s
          ),
          sources: {
            status: res.sources.length > 0 ? "ready" : "empty",
            items: res.sources,
          },
          metrics: {
            usedContext: res.used_context,
            cacheHit: res.cache_hit,
            cacheType: res.cache_type,
            timing: res.timing,
            firstTokenMs:
              baseDiag.metrics.firstTokenMs ??
              (res.prompt_diagnostics &&
              typeof res.prompt_diagnostics === "object" &&
              "time_to_first_token_ms" in res.prompt_diagnostics
                ? Number((res.prompt_diagnostics as Record<string, unknown>).time_to_first_token_ms)
                : undefined),
          },
          retrievalDebug: (res.retrieval_debug as Record<string, unknown> | null) ?? baseDiag.retrievalDebug,
          promptDiagnostics: res.prompt_diagnostics ?? baseDiag.promptDiagnostics,
          trace: res.trace ?? baseDiag.trace,
          metadata: res.metadata ?? baseDiag.metadata,
          understandingTrace: res.understanding_trace ?? baseDiag.understandingTrace,
        },
      };
    }
    case "error":
      return {
        ...turn,
        status: "error",
        text: turn.text || event.message,
        diagnostics: {
          ...baseDiag,
          status: "error",
          errorMessage: event.message,
        },
      };
    default:
      return turn;
  }
}

export function finalizeFromResponse(turn: ChatTurn, response: ChatResponse): ChatTurn {
  return reduceStreamEvent(turn, { type: "final", response });
}
