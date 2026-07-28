import axios from "axios";
import type {
  AnalyticsInsightsPayload,
  AnalyticsSummary,
  AuthLoginResponse,
  AuthUser,
  ChatLogList,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionList,
  HealthResponse,
  IntentDistributionRow,
  OverviewResponse,
  IndexJobStatus,
  IndexQueuePreview,
  KnowledgeProfile,
  KnowledgeProfilePreset,
  PopularQueryRow,
  ProblematicQueryRow,
  ProductAnalyticsSummary,
  ProfileGenerationJobStatus,
  LlmBenchmarkResponse,
  LlmRuntimeInfo,
  OllamaDeleteResponse,
  OllamaModel,
  OllamaPullResponse,
  PerformanceStatus,
  RetrievalQualityMetrics,
  Settings,
  SlowQuery,
  Source,
  SourceAnalyticsPayload,
  SourceDetail,
  SourceList,
  SourceListFilters,
  TimeseriesPoint,
  TopicDistributionRow,
  TensionList,
  BuildInfo,
  UnansweredQuery,
  UserCreatePayload,
  UserRecord,
  UserUpdatePayload,
} from "../types";
import {
  type ChatStreamCallbacks,
  createChatStreamState,
  parseChatStreamChunk,
} from "../lib/chatStreamParser";

export type { ChatStreamCallbacks };

const api = axios.create({ baseURL: "" });

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

api.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      authToken &&
      !String(error.config?.url || "").includes("/api/auth/login") &&
      !window.location.pathname.startsWith("/login")
    ) {
      try {
        localStorage.removeItem("ai-site-agent-auth-token");
      } catch {
        /* ignore */
      }
      authToken = null;
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const login = async (username: string, password: string): Promise<AuthLoginResponse> =>
  (await api.post("/api/auth/login", { username, password })).data;

export const logout = async (): Promise<void> => {
  await api.post("/api/auth/logout");
};

export const getMe = async (): Promise<AuthUser> => (await api.get("/api/auth/me")).data;

export const listUsers = async (): Promise<UserRecord[]> => (await api.get("/api/users")).data;

export const listUnderstandingTensions = async (params?: {
  page?: number;
  page_size?: number;
  claim_limit?: number;
}): Promise<TensionList> =>
  (await api.get("/api/understanding/tensions", { params })).data;

export const getBuildInfo = async (): Promise<BuildInfo> =>
  (await api.get("/api/build")).data;

export const createUser = async (payload: UserCreatePayload): Promise<UserRecord> =>
  (await api.post("/api/users", payload)).data;

export const updateUser = async (id: number, payload: UserUpdatePayload): Promise<UserRecord> =>
  (await api.put(`/api/users/${id}`, payload)).data;

export const changeUserPassword = async (id: number, password: string): Promise<void> => {
  await api.post(`/api/users/${id}/change-password`, { password });
};

export const deactivateUser = async (id: number): Promise<UserRecord> =>
  (await api.post(`/api/users/${id}/deactivate`)).data;

export const activateUser = async (id: number): Promise<UserRecord> =>
  (await api.post(`/api/users/${id}/activate`)).data;

export const deleteUser = async (id: number): Promise<void> => {
  await api.delete(`/api/users/${id}`);
};

export const getHealth = async (): Promise<HealthResponse> =>
  (await api.get("/api/health")).data;

export const getOverview = async (): Promise<OverviewResponse> =>
  (await api.get("/api/overview")).data;

export const getSettings = async (): Promise<Settings> =>
  (await api.get("/api/settings")).data;

export const updateSettings = async (s: Partial<Settings>): Promise<Settings> =>
  (await api.put("/api/settings", s)).data;

export const getKnowledgeProfile = async (): Promise<KnowledgeProfile> =>
  (await api.get("/api/knowledge-profile")).data;

export const updateKnowledgeProfile = async (
  profile: KnowledgeProfile
): Promise<KnowledgeProfile> =>
  (await api.put("/api/knowledge-profile", { profile })).data;

export const getKnowledgeProfilePresets = async (): Promise<KnowledgeProfilePreset[]> =>
  (await api.get("/api/knowledge-profile/presets")).data;

export const loadKnowledgeProfilePreset = async (
  presetId: string
): Promise<KnowledgeProfile> =>
  (await api.post("/api/knowledge-profile/presets/load", { preset_id: presetId })).data;

export const exportKnowledgeProfile = async (): Promise<KnowledgeProfile> =>
  (await api.get("/api/knowledge-profile/export")).data;

export const importKnowledgeProfile = async (
  profile: KnowledgeProfile
): Promise<KnowledgeProfile> =>
  (await api.post("/api/knowledge-profile/import", { profile })).data;

export const startKnowledgeProfileGeneration = async (body: {
  use_llm?: boolean;
  merge_identity?: boolean;
  sections?: string[];
}): Promise<ProfileGenerationJobStatus> =>
  (await api.post("/api/knowledge-profile/generate/start", body)).data;

export const getKnowledgeProfileGenerationStatus =
  async (): Promise<ProfileGenerationJobStatus> =>
    (await api.get("/api/knowledge-profile/generate/status")).data;

export const applyGeneratedKnowledgeProfile = async (
  profile: KnowledgeProfile,
  sections?: string[]
): Promise<{ profile: KnowledgeProfile }> =>
  (await api.post("/api/knowledge-profile/generate/apply", { profile, sections })).data;

export const exportKnowledgeProfileGenerationReport = async (
  jobId: number
): Promise<unknown> =>
  (await api.get(`/api/knowledge-profile/generate/${jobId}/export-report`)).data;

export const listSources = async (
  filters: SourceListFilters = {}
): Promise<SourceList> =>
  (
    await api.get("/api/sources", {
      params: { page: 1, page_size: 50, ...filters },
    })
  ).data;

export const getSource = async (id: number): Promise<SourceDetail> =>
  (await api.get(`/api/sources/${id}`)).data;

export const exportSources = async (): Promise<void> => {
  const response = await api.get("/api/sources/export", { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "sources-export.json");
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const bulkReindexSources = async (ids: number[]): Promise<{ message: string }> =>
  (await api.post("/api/sources/bulk/reindex", { ids })).data;

export const bulkDeleteSources = async (ids: number[]): Promise<{ message: string }> =>
  (await api.post("/api/sources/bulk/delete", { ids })).data;

export const bulkResetSourceStatus = async (ids: number[]): Promise<{ message: string }> =>
  (await api.post("/api/sources/bulk/reset-status", { ids })).data;

export const deleteSource = async (id: number): Promise<void> => {
  await api.delete(`/api/sources/${id}`);
};

export const reindexSource = async (id: number): Promise<Source> =>
  (await api.post(`/api/sources/${id}/reindex`)).data;

export const startIndexing = async (
  payload: Record<string, unknown>
): Promise<{ message: string }> =>
  (await api.post("/api/index/start", payload)).data;

export const stopIndexing = async (): Promise<{ message: string }> =>
  (await api.post("/api/index/stop")).data;

export const reindexAll = async (): Promise<{ message: string }> =>
  (await api.post("/api/index/reindex-all")).data;

export const reprocessExisting = async (payload: {
  scope?: string;
  source_ids?: number[];
  dry_run?: boolean;
  limit?: number | null;
  needs_reprocess_only?: boolean;
}): Promise<{
  job_id: string;
  status: string;
  selected_sources: number;
  estimated_chunks?: number;
  sample_boilerplate_ratios?: number[];
}> => (await api.post("/api/index/reprocess-existing", payload)).data;

export const generateSourceIntelligence = async (payload: {
  scope?: string;
  source_ids?: number[];
  dry_run?: boolean;
  limit?: number | null;
  generate_summaries?: boolean;
}): Promise<{
  job_id?: string;
  status: string;
  selected_sources: number;
  updated_sources?: number;
  sample_profiles?: Record<string, unknown>[];
}> => (await api.post("/api/index/generate-source-intelligence", payload)).data;

export const getSourceIntelligenceStats = async (): Promise<{
  sources_needing_intelligence: number;
  sources_up_to_date: number;
  total_indexed: number;
  estimated_llm_calls: number;
  estimated_skips: number;
  worker_count: number;
  batch_size: number;
  page_size: number;
}> => (await api.get("/api/index/source-intelligence-stats")).data;

export const getIndexStatus = async (): Promise<IndexJobStatus> =>
  (await api.get("/api/index/status")).data;

export const getIndexQueuePreview = async (): Promise<IndexQueuePreview> =>
  (await api.get("/api/index/queue-preview")).data;

export const sendChat = async (
  message: string,
  sessionId: string | null,
  debug = true,
  bypassCache = false,
  skipUserMessage = false
): Promise<ChatResponse> =>
  (
    await api.post("/api/chat", {
      message,
      session_id: sessionId,
      debug,
      bypass_cache: bypassCache,
      skip_user_message: skipUserMessage,
    })
  ).data;

export const sendChatStream = async (
  message: string,
  sessionId: string | null,
  callbacks: ChatStreamCallbacks,
  bypassCache = false,
  debug = true,
  signal?: AbortSignal
): Promise<ChatResponse> => {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers,
    signal,
    body: JSON.stringify({
      message,
      session_id: sessionId,
      bypass_cache: bypassCache,
      debug,
    }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`stream failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const state = createChatStreamState();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer = parseChatStreamChunk(decoder.decode(value, { stream: true }), buffer, state, callbacks);
  }
  if (!state.finalResponse) {
    throw new Error("stream ended without final event");
  }
  return state.finalResponse;
};

export const clearRetrievalCache = async () =>
  (await api.post("/api/settings/cache/clear-retrieval")).data;

export const clearAnswerCache = async () =>
  (await api.post("/api/settings/cache/clear-answer")).data;

export const clearAllCaches = async () =>
  (await api.post("/api/settings/cache/clear-all")).data;

export const getCurrentChatSession = async (
  sessionId: string
): Promise<ChatSessionDetail> =>
  (await api.get("/api/chat/sessions/current", { params: { session_id: sessionId } })).data;

export const createChatSession = async (
  closeCurrentSessionId: string | null
): Promise<ChatSessionDetail> =>
  (
    await api.post("/api/chat/sessions", {
      close_current_session_id: closeCurrentSessionId,
    })
  ).data;

export const getChatSession = async (sessionId: string): Promise<ChatSessionDetail> =>
  (await api.get(`/api/chat/sessions/${sessionId}`)).data;

export const listChatSessions = async (
  page = 1,
  pageSize = 50,
  params?: { status?: string; query?: string }
): Promise<ChatSessionList> =>
  (
    await api.get("/api/chat/sessions", {
      params: { page, page_size: pageSize, ...params },
    })
  ).data;

export const clearChatSession = async (sessionId: string): Promise<ChatSessionDetail> =>
  (await api.post(`/api/chat/sessions/${sessionId}/clear`)).data;

export const closeChatSession = async (sessionId: string) =>
  (await api.post(`/api/chat/sessions/${sessionId}/close`)).data;

export const getChatLogs = async (
  page = 1,
  pageSize = 50,
  sessionId?: string | null
): Promise<ChatLogList> =>
  (
    await api.get("/api/chat/logs", {
      params: {
        page,
        page_size: pageSize,
        ...(sessionId ? { session_id: sessionId } : {}),
      },
    })
  ).data;

export const getModels = async (): Promise<{ models: OllamaModel[]; ollama_reachable?: boolean }> =>
  (await api.get("/api/models")).data;

export const pullOllamaModel = async (model: string): Promise<OllamaPullResponse> =>
  (await api.post("/api/ollama/models/pull", { model }, { timeout: 600_000 })).data;

export const deleteOllamaModel = async (model: string): Promise<OllamaDeleteResponse> =>
  (await api.post("/api/ollama/models/delete", { model })).data;

export const getLlmRuntimeInfo = async (): Promise<LlmRuntimeInfo> =>
  (await api.get("/api/llm/runtime")).data;

export const runLlmBenchmark = async (): Promise<LlmBenchmarkResponse> =>
  (await api.post("/api/llm/benchmark")).data;

export const getAnalyticsSummary = async (): Promise<AnalyticsSummary> =>
  (await api.get("/api/analytics/summary")).data;

export const getProductAnalyticsSummary = async (
  periodDays = 7
): Promise<ProductAnalyticsSummary> =>
  (await api.get("/api/analytics/product-summary", { params: { period_days: periodDays } })).data;

export const getAnalyticsTimeseries = async (
  hours = 24
): Promise<TimeseriesPoint[]> =>
  (await api.get("/api/analytics/timeseries", { params: { hours } })).data;

export const getPopularQueries = async (
  limit = 20,
  search = "",
  periodDays = 30
): Promise<PopularQueryRow[]> =>
  (
    await api.get("/api/analytics/popular-queries", {
      params: { limit, search, period_days: periodDays },
    })
  ).data;

export const getProblematicQueries = async (
  limit = 20,
  periodDays = 30
): Promise<ProblematicQueryRow[]> =>
  (
    await api.get("/api/analytics/problematic-queries", {
      params: { limit, period_days: periodDays },
    })
  ).data;

export const getRetrievalQuality = async (
  periodDays = 7
): Promise<RetrievalQualityMetrics> =>
  (await api.get("/api/analytics/retrieval-quality", { params: { period_days: periodDays } })).data;

export const getSourceAnalytics = async (
  topLimit = 15,
  unusedLimit = 15
): Promise<SourceAnalyticsPayload> =>
  (
    await api.get("/api/analytics/sources", {
      params: { top_limit: topLimit, unused_limit: unusedLimit },
    })
  ).data;

export const getIntentDistribution = async (
  periodDays = 30
): Promise<IntentDistributionRow[]> =>
  (await api.get("/api/analytics/intents", { params: { period_days: periodDays } })).data;

export const getTopicDistribution = async (
  periodDays = 30,
  limit = 12
): Promise<TopicDistributionRow[]> =>
  (await api.get("/api/analytics/topics", { params: { period_days: periodDays, limit } })).data;

export const getAnalyticsInsights = async (
  periodDays = 7
): Promise<AnalyticsInsightsPayload> =>
  (await api.get("/api/analytics/insights", { params: { period_days: periodDays } })).data;

export const getTopUnanswered = async (
  limit = 10
): Promise<UnansweredQuery[]> =>
  (await api.get("/api/analytics/top-unanswered", { params: { limit } })).data;

export const getSlowQueries = async (limit = 10): Promise<SlowQuery[]> =>
  (await api.get("/api/analytics/slow-queries", { params: { limit } })).data;

export const getSystemPerformance = async (): Promise<PerformanceStatus> =>
  (await api.get("/api/system/performance")).data;

export default api;
