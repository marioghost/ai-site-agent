import type {
  CacheType,
  ChatResponse,
  ChatSource,
  RequestMetadata,
  TimingMetrics,
  TracePayload,
  UnderstandingTrace,
} from "../types";

export type MessageStatus = "pending" | "streaming" | "completed" | "truncated" | "error" | "cancelled";

export type PipelineStageStatus = "pending" | "running" | "completed" | "error" | "skipped";

export interface PipelineStage {
  id: string;
  name: string;
  status: PipelineStageStatus;
  durationMs?: number;
}

export interface SourcesState {
  status: "loading" | "ready" | "empty";
  items: ChatSource[];
}

export interface MetricsState {
  usedContext?: boolean;
  cacheHit?: boolean;
  cacheType?: CacheType;
  timing: Partial<TimingMetrics>;
  firstTokenMs?: number;
}

/** Progressive + final diagnostics bundle stored on each assistant turn. */
export interface AssistantDiagnostics {
  requestId: string;
  sessionId: string;
  status: MessageStatus;
  pipeline: PipelineStage[];
  sources: SourcesState;
  metrics: MetricsState;
  retrievalDebug: Record<string, unknown> | null;
  promptDiagnostics: Record<string, unknown> | null;
  trace: TracePayload | null;
  metadata: RequestMetadata | null;
  understandingTrace: UnderstandingTrace | null;
  errorMessage?: string;
}

export type StreamEvent =
  | { type: "start"; requestId: string; sessionId: string; messageId?: string }
  | { type: "pipeline.status"; stage: string; status: string; durationMs?: number }
  | { type: "retrieval"; sources: ChatSource[]; retrievalDebug?: Record<string, unknown> | null; tracePartial?: TracePayload | null; usedContext?: boolean; cacheHit?: boolean; cacheType?: string }
  | { type: "diagnostics"; promptDiagnostics?: Record<string, unknown> | null; timingPartial?: Partial<TimingMetrics> }
  | { type: "token"; delta: string }
  | { type: "llm.first_token"; timeToFirstTokenMs: number }
  | { type: "final"; response: ChatResponse }
  | { type: "error"; message: string };
