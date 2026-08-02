export interface HealthComponent {
  status: string;
  detail?: string | null;
}

export interface DatabaseHealth extends HealthComponent {
  engine?: string;
  migration_version?: string | null;
  latency_ms?: number | null;
  pool?: string | null;
}

export interface HealthResponse {
  app: HealthComponent;
  ollama: HealthComponent;
  qdrant: HealthComponent;
  database: DatabaseHealth;
}

export interface KnowledgeBaseStatus {
  total_sources: number;
  ready_to_use: number;
  waiting: number;
  needs_refresh: number;
  failed: number;
  skipped: number;
  readiness_percent: number;
  ready_pages: number;
  ready_files: number;
  waiting_pages: number;
  waiting_files: number;
  chunks_count: number;
  vectors_count: number;
  last_indexed_at: string | null;
}

export interface OverviewResponse {
  knowledge_base: KnowledgeBaseStatus;
}

export type ScanMode = "pages_only" | "pages_and_files" | "files_only";
export type RetrievalMode = "dense" | "lexical" | "hybrid";

export interface Settings {
  id: number;
  site_url: string | null;
  sitemap_url: string | null;
  crawl_depth: number;
  allowed_domains: string[];
  deny_url_patterns: string[];
  allowed_file_types: string[];
  scan_mode: ScanMode;
  enable_file_indexing: boolean;
  scan_all_pages: boolean;
  scan_all_files: boolean;
  llm_model: string;
  embedding_model: string;
  qdrant_collection: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  similarity_threshold: number;
  temperature: number;
  max_tokens: number;
  system_prompt: string;
  fallback_answer: string;
  enable_sources: boolean;
  enable_chat_logs: boolean;
  request_timeout_seconds: number;
  max_pages_per_run: number;
  max_files_per_run: number;
  indexed_page_refresh_interval_hours: number;
  indexed_file_refresh_interval_hours: number;
  default_response_language: string;
  dashboard_language: "uk" | "en";
  enable_source_links: boolean;
  enable_reranking: boolean;
  enable_ukrainian_polish_pass: boolean;
  fast_mode_enabled: boolean;
  enable_retrieval_cache: boolean;
  enable_semantic_answer_cache: boolean;
  retrieval_cache_ttl_seconds: number;
  answer_cache_ttl_seconds: number;
  semantic_cache_similarity_threshold: number;
  max_cached_answers: number;
  knowledge_version?: number | null;
  retrieval_mode: RetrievalMode;
  enable_query_expansion: boolean;
  enable_retrieval_debug: boolean;
  enable_intent_aware_retrieval: boolean;
  enable_canonical_source_selection: boolean;
  enable_news_deprioritization_for_overview_queries: boolean;
  fallback_second_pass_enabled: boolean;
  enable_broad_question_mode: boolean;
  enable_context_builder: boolean;
  retrieval_candidate_count: number;
  max_pages_in_context: number;
  max_chunks_per_page: number;
  retrieval_profile?: string;
  document_priorities_json?: string;
  intent_profiles_json?: string;
  scoring_weights_json?: string;
  top_k_dense?: number | null;
  top_k_lexical?: number | null;
  rerank_limit?: number | null;
  document_limit?: number | null;
  minimum_retrieval_score?: number | null;
  enable_tracing: boolean;
  enable_trace_storage: boolean;
  enable_request_metadata_logging: boolean;
  enable_chat_debug_payload: boolean;
  enable_semantic_diagnostics_v2: boolean;
  cache_namespace_v2_enabled?: boolean;
  memory_shadow_write_enabled?: boolean;
  memory_evidence_assist_enabled?: boolean;
  memory_canonical_shadow_enabled?: boolean;
  allow_legacy_kp_presets?: boolean;
  legacy_doc_type_canonical_enabled?: boolean;
  max_trace_retention_days: number;
  max_concurrent_chat_requests: number;
  max_concurrent_llm_requests: number;
  max_concurrent_embedding_requests: number;
  max_concurrent_background_embedding_requests: number;
  chat_total_timeout_seconds: number;
  ollama_generation_timeout_seconds: number;
  ollama_embedding_timeout_seconds: number;
  qdrant_timeout_seconds: number;
  polish_mode?: string;
  polish_min_answer_chars?: number;
  polish_timeout_seconds?: number;
  polish_model?: string;
  llm_num_predict?: number;
  llm_num_ctx_mode?: string;
  llm_fixed_num_ctx?: number;
  llm_max_prompt_chars?: number;
  llm_keep_alive?: string;
  max_sources_in_prompt?: number;
  max_chars_per_source?: number;
  max_total_context_chars?: number;
  prefer_user_language_sources?: boolean;
  enable_source_intelligence?: boolean;
  enable_llm_source_intelligence?: boolean;
  source_intelligence_importance_threshold?: number;
  source_intelligence_worker_count?: number;
  run_source_intelligence_inline_during_indexing?: boolean;
  penalize_campaigns_for_overview?: boolean;
  llm_mode_profile?: string;
  enable_llm_warmup?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RetrievalDebugItem {
  title: string;
  url: string;
  heading: string;
  content_type_hint: string;
  is_homepage: boolean;
  dense_score: number;
  lexical_score: number;
  final_score: number;
  used: boolean;
}

export interface RetrievalDebug {
  normalized_query: string;
  variants: string[];
  match_query: string;
  mode: string;
  short_query: boolean;
  similarity_threshold: number;
  dense: RetrievalDebugItem[];
  lexical: RetrievalDebugItem[];
  final: RetrievalDebugItem[];
}

export interface Source {
  id: number;
  source_type: string;
  url: string;
  title: string | null;
  document_type?: string | null;
  content_hash: string | null;
  content_length: number;
  status: string;
  display_status?: string | null;
  chunk_count?: number;
  error_message: string | null;
  indexed_at: string | null;
  last_checked_at?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SourceSemanticProfile {
  main_topic?: string;
  main_topic_confidence?: number;
  subtopics?: string[];
  document_purpose?: string;
  document_purpose_confidence?: number;
  entity_type?: string;
  entity_type_confidence?: number;
  supported_intents?: string[];
  search_keywords?: string[];
  synonyms?: string[];
  semantic_tags?: string[];
  suitable_for?: string[];
  not_suitable_for?: string[];
  confidence?: number;
  generator?: string;
  generated_at?: string | null;
}

export interface SourceDetail extends Source {
  preview_text: string;
  word_count: number;
  char_count: number;
  content_type_hint: string;
  semantic_profile?: SourceSemanticProfile;
  profile_version?: string;
  llm_summary?: string;
}

export type ProvenanceScope = "real" | "test" | "all";

export interface TensionRecord {
  tension_type: string;
  claim_ids: number[];
  observation_ref_ids: number[];
  evidence_link_ids: number[];
  summary: string;
  provenance_scope?: string;
  claim_provenance_kinds?: string[];
  is_test_data?: boolean;
}

export interface TensionList {
  items: TensionRecord[];
  total: number;
  page: number;
  page_size: number;
  provenance_scope?: ProvenanceScope;
}

export interface EpistemicHealthSummary {
  real_claims: number;
  test_claims: number;
  real_active_claims: number;
  test_active_claims: number;
  real_superseded_claims: number;
  test_superseded_claims: number;
  real_observations: number;
  test_observations: number;
  real_evidence_links: number;
  test_evidence_links: number;
  source_intelligence_claims: number;
  real_support_deficit_tensions: number;
  real_conflict_tensions: number;
  real_open_tensions: number;
  test_open_tensions: number;
  memory_version: number;
  memory_shadow_write_enabled: boolean;
  chat_impact: "not_active";
  diagnostic_only: boolean;
  experimental: boolean;
}

export interface DeployedCapability {
  supported: boolean;
  value: boolean | null;
  surface: string;
  friendly_name: string;
  default: boolean;
  effect: string;
  rollout: string;
  classification?: string | null;
  runtime_owner?: string | null;
  effective?: boolean | null;
  skipped_reason?: string | null;
}

/** Additive typed maintenance observation (Step 065). Not in env_flags bool maps. */
export interface MaintenanceObservation {
  execution_enabled: boolean;
  investigations_per_cycle: number;
  surface: string;
  runtime_owner: string;
}

export interface ReleaseStatus {
  accepted: string;
  in_progress: string | null;
  closed_0_6?: boolean;
  closed_0_7?: boolean;
  closed_0_8?: boolean;
  engineering_ready?: boolean;
  staging_validated?: boolean;
  production_ready?: boolean;
  note: string;
}

export interface BuildInfo {
  app_version: string;
  release: string;
  git_commit: string | null;
  git_commit_short: string | null;
  build_time: string | null;
  alembic_head: string | null;
  memory_version: number;
  knowledge_version: number;
  feature_flags: Record<string, boolean>;
  env_flags: Record<string, boolean>;
  settings_flags: Record<string, boolean>;
  maintenance_observation?: MaintenanceObservation | null;
  release_status: ReleaseStatus | null;
  deployed_capabilities: Record<string, DeployedCapability>;
}

export interface SourceList {
  items: Source[];
  total: number;
  page: number;
  page_size: number;
}

export interface SourceListFilters {
  page?: number;
  page_size?: number;
  search?: string;
  bucket?: string;
  source_type?: string;
  url_contains?: string;
  date_range?: string;
  status?: string;
  exclude_fixtures?: boolean;
}

export interface IndexLogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export interface IndexActivityEntry {
  time: string;
  level: string;
  message: string;
}

export interface IndexRunProgress {
  selected_total: number;
  processed_total: number;
  selected_pages: number;
  selected_files: number;
  processed_pages: number;
  processed_files: number;
  percent: number | null;
  is_indeterminate: boolean;
}

export interface IndexRunSummary {
  found_pages: number;
  found_files: number;
  selected_pages: number;
  selected_files: number;
  processed_pages: number;
  processed_files: number;
  added: number;
  updated: number;
  unchanged: number;
  skipped: number;
  errors: number;
}

export interface IndexAdvancedStatus {
  current_phase?: string | null;
  discovery?: IndexDiscoveryStatus;
  queue?: IndexQueueStatus;
  pages?: IndexPagesStatus;
  files?: IndexFilesStatus;
  errors_count?: number;
  log?: IndexLogEntry[];
}

export interface IndexDiscoveryStatus {
  discovered_urls: number;
  discovered_pages: number;
  discovered_files: number;
  already_known_urls: number;
  newly_discovered_urls: number;
}

export interface IndexQueueStatus {
  new_pages_waiting: number;
  failed_pages_waiting: number;
  stale_pages_waiting: number;
  fresh_pages_skipped_until_refresh: number;
  queued_pages_for_this_run: number;
  total_pages_waiting: number;
}

export interface IndexPagesStatus {
  processed_pages: number;
  indexed_new_pages: number;
  updated_pages: number;
  unchanged_pages: number;
  skipped_empty_pages: number;
  skipped_fresh_pages: number;
  failed_pages: number;
}

export interface IndexFilesStatus {
  discovered_files: number;
  queued_files_for_this_run: number;
  processed_files: number;
  indexed_new_files: number;
  updated_files: number;
  unchanged_files: number;
  skipped_files: number;
  failed_files: number;
}

export interface IndexJobStatus {
  id: number | null;
  status: string;
  current_phase?: string | null;
  stage?: string;
  run_mode?: string | null;
  current_url: string | null;
  current_url_type?: string | null;
  current_action?: string | null;
  last_activity_at?: string | null;
  last_activity_message?: string | null;
  heartbeat_counter?: number;
  alive_state?: string;
  seconds_since_activity?: number | null;
  started_at: string | null;
  updated_at?: string | null;
  finished_at: string | null;
  progress?: IndexRunProgress;
  summary?: IndexRunSummary;
  recent_activity?: IndexActivityEntry[];
  advanced?: IndexAdvancedStatus | null;
  discovery?: IndexDiscoveryStatus;
  queue?: IndexQueueStatus;
  pages?: IndexPagesStatus;
  files?: IndexFilesStatus;
  log_tail?: IndexLogEntry[];
  /** Legacy flat fields */
  discovered_pages: number;
  new_pages: number;
  queued_pages: number;
  processed_pages: number;
  indexed_pages: number;
  unchanged_pages: number;
  skipped_pages: number;
  skipped_fresh_pages: number;
  failed_pages: number;
  stale_pages: number;
  discovered_files: number;
  indexed_files: number;
  skipped_files: number;
  errors_count: number;
  log: IndexLogEntry[];
  intelligence_sample_profiles?: Array<Record<string, unknown>>;
  intelligence_selected_sources?: number;
  intelligence_updated_sources?: number;
  dry_run?: boolean;
  skipped_unchanged?: number;
  would_skip_unchanged?: number;
  would_call_llm?: number;
  llm_cache_hits?: number;
  llm_calls?: number;
  llm_failures?: number;
  avg_ms_per_source?: number;
  estimated_time_with_llm?: number;
  estimated_remaining_seconds?: number | null;
  worker_count?: number;
  batch_size?: number;
  selected_sources?: number;
}

export interface IndexQueuePreview {
  queue?: IndexQueueStatus;
  max_pages_per_run?: number;
  estimated_runs_remaining?: number;
  /** Legacy flat fields */
  new_pages: number;
  failed_pages: number;
  skipped_pages_waiting: number;
  stale_pages: number;
  fresh_pages: number;
  queued_pages: number;
  total_sources: number;
}

export interface ChatSource {
  title: string;
  url: string;
  source_type: string;
  score: number;
}

export type CacheType =
  | "none"
  | "retrieval"
  | "retrieval_success"
  | "retrieval_empty"
  | "retrieval_error"
  | "answer"
  | "answer_success"
  | "answer_fallback";

export interface CacheStatus {
  answer_cache_hit: boolean;
  retrieval_cache_hit: boolean;
  cache_type: string;
  cache_age_seconds?: number | null;
  cache_key?: string | null;
  cache_namespace?: Record<string, string> | null;
  cache_ttl_seconds?: number | null;
  cached_selected_chunk_count: number;
  cached_context_used: boolean;
  negative_cache: boolean;
  bypassed: boolean;
  invalidation_version?: string | null;
}

export interface TimingMetrics {
  total_ms: number;
  retrieval_ms: number;
  generation_ms: number;
  polish_ms: number;
}

export interface TraceStep {
  name: string;
  status: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface RetrievedChunk {
  title: string;
  url: string;
  source_type: string;
  heading: string;
  document_type: string;
  content_type_hint: string;
  dense_score: number;
  lexical_score: number;
  final_score: number;
  used_in_context: boolean;
  is_canonical: boolean;
  excluded_as_news: boolean;
  text_preview: string;
}

export interface TracePayload {
  steps: TraceStep[];
  retrieved_chunks: RetrievedChunk[];
}

export interface RequestMetadata {
  request_id: string;
  session_id: string | null;
  user_ip: string | null;
  user_agent: string | null;
  referrer: string | null;
  knowledge_version: number;
  retrieval_mode: string;
  query_intent: string;
  applied_knowledge_config?: AppliedKnowledgeConfig | null;
  created_at: string | null;
}

export interface UnderstandingTraceStep {
  phase: string;
  status: "pending" | "skipped" | "completed" | "failed";
  summary?: string | null;
  duration_ms?: number | null;
  evidence_count?: number | null;
  confidence?: number | null;
  details?: Record<string, unknown>;
}

export interface UnderstandingTrace {
  version: string;
  populated: boolean;
  summary?: string | null;
  steps: UnderstandingTraceStep[];
}

export interface ChatResponse {
  session_id: string;
  request_id: string;
  answer: string;
  sources: ChatSource[];
  used_context: boolean;
  cache_hit: boolean;
  cache_type: CacheType;
  cache?: CacheStatus | null;
  timing: TimingMetrics;
  trace?: TracePayload | null;
  metadata?: RequestMetadata | null;
  retrieval_debug?: RetrievalDebug | null;
  error_type?: string | null;
  prompt_diagnostics?: Record<string, unknown> | null;
  understanding_trace?: UnderstandingTrace | null;
}

export interface AnalyticsSummary {
  total_requests: number;
  requests_today: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  cache_hit_rate: number;
  fallback_rate: number;
  context_usage_rate: number;
  error_count: number;
}

export interface TimeseriesPoint {
  hour: string;
  requests: number;
  avg_latency_ms: number;
  cache_hit_rate: number;
  fallback_rate?: number;
  context_usage_rate?: number;
}

export interface MetricTrend {
  value: number;
  previous_value: number;
  change_pct: number | null;
  direction: "up" | "down" | "neutral";
}

export interface ProductAnalyticsSummary {
  total_conversations: number;
  total_messages: number;
  unique_users: number;
  total_requests: number;
  successful_responses: number;
  success_rate: number;
  context_usage_rate: number;
  cache_hit_rate: number;
  fallback_rate: number;
  average_latency_ms: number;
  trends: Record<string, MetricTrend>;
}

export interface PopularQueryRow {
  query: string;
  count: number;
  avg_response_ms: number;
  cache_hit_rate: number;
  fallback_count: number;
  success_rate: number;
}

export interface ProblematicQueryRow {
  query: string;
  occurrences: number;
  fallback_count: number;
  timeout_count: number;
  retrieval_failure_count: number;
  avg_retrieval_score: number;
}

export interface RetrievalQualityMetrics {
  avg_retrieval_score: number;
  avg_rerank_score: number;
  avg_chunk_count: number;
  avg_context_chars: number;
  avg_prompt_chars: number;
  context_usage_rate: number;
  responses_without_context: number;
  avg_retrieval_ms: number;
  avg_generation_ms: number;
}

export interface SourceUsageRow {
  title: string;
  url: string;
  usage_count: number;
  avg_score: number;
  last_used_at: string | null;
}

export interface UnusedSourceRow {
  title: string;
  url: string;
  indexed_at: string | null;
  document_type: string;
}

export interface SourceAnalyticsPayload {
  top_pages: SourceUsageRow[];
  unused_sources: UnusedSourceRow[];
}

export interface IntentDistributionRow {
  intent: string;
  count: number;
  share: number;
}

export interface TopicDistributionRow {
  topic_key: string;
  topic_label: string;
  count: number;
  share: number;
}

export interface AnalyticsInsight {
  id: string;
  severity: "info" | "warning" | "success";
  message_key: string;
  params?: Record<string, string | number>;
}

export interface AnalyticsRecommendation {
  id: string;
  stars: number;
  message_key: string;
  params?: Record<string, string | number>;
}

export interface AnalyticsInsightsPayload {
  insights: AnalyticsInsight[];
  recommendations: AnalyticsRecommendation[];
}

export interface UnansweredQuery {
  query: string;
  count: number;
}

export interface SlowQuery {
  request_id: string;
  query: string;
  total_ms: number;
  cache_hit: boolean;
  created_at: string | null;
}

export interface PerformanceStatus {
  active_requests: number;
  queued_requests: number;
  max_concurrent_llm_requests: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  cache_hit_rate: number;
  ollama_status: string;
  qdrant_status: string;
}

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  messageId?: number;
  status?: import("../chat/types").MessageStatus;
  diagnostics?: import("../chat/types").AssistantDiagnostics;
  sources?: ChatSource[];
  usedContext?: boolean;
  cacheHit?: boolean;
  cacheType?: CacheType;
  timing?: TimingMetrics;
  trace?: TracePayload | null;
  metadata?: RequestMetadata | null;
  response?: ChatResponse | null;
}

export interface ChatMessage {
  id: number;
  session_id: string;
  role: string;
  content: string;
  sources: ChatSource[];
  request_id: string | null;
  trace_id: string | null;
  used_context: boolean;
  cache_hit: boolean;
  cache_type: CacheType;
  timing: TimingMetrics;
  diagnostics?: Record<string, unknown> | null;
  created_at: string | null;
}

export interface ChatSession {
  session_id: string;
  title: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  closed_at: string | null;
  last_message_at: string | null;
  message_count: number;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface ChatSessionList {
  items: ChatSession[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChatLog {
  id: number;
  session_id: string | null;
  request_id: string | null;
  user_message: string;
  assistant_answer: string;
  used_context: boolean;
  sources: ChatSource[];
  cache_hit: boolean;
  cache_type: CacheType;
  retrieval_ms: number;
  generation_ms: number;
  polish_ms: number;
  created_at: string | null;
}

export interface ChatLogList {
  items: ChatLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface OllamaModel {
  name: string;
  size?: number | null;
  modified_at?: string | null;
  family?: string | null;
  parameter_size?: string | null;
  in_use_as?: "llm" | "embedding" | null;
}

export interface OllamaPullResponse {
  model: string;
  status: string;
  duration_ms: number;
  message?: string;
}

export interface OllamaDeleteResponse {
  model: string;
  status: string;
  message?: string;
}

export interface LlmBenchmarkScenario {
  key: string;
  error?: string | null;
  answer_preview?: string;
  total_duration_ms: number;
  load_duration_ms?: number | null;
  prompt_eval_duration_ms?: number | null;
  eval_duration_ms?: number | null;
  prompt_eval_count?: number | null;
  eval_count?: number | null;
  tokens_per_second: number;
  time_to_first_token_ms?: number | null;
  connection_ms?: number | null;
  model: string;
  options?: Record<string, unknown>;
}

export interface LlmBenchmarkResponse {
  model: string;
  options: Record<string, unknown>;
  model_warm: boolean;
  warmup_status: string;
  environment: Record<string, unknown>;
  scenarios: LlmBenchmarkScenario[];
}

export interface LlmRuntimeInfo {
  ollama_reachable: boolean;
  ollama_detail?: string | null;
  ollama_version?: string | null;
  active_model: string;
  model_installed?: boolean;
  installed_models?: string[];
  warmup: Record<string, unknown>;
  environment: Record<string, unknown>;
  recommended_models: Array<Record<string, string>>;
}

export type { AuthUser, AuthLoginResponse, UserRecord, UserCreatePayload, UserUpdatePayload, UserRole } from "./auth";


export interface ImportantTopic {
  key: string;
  label: string;
  aliases: string[];
  preferred_document_types: string[];
  preferred_content_hints: string[];
  answer_strategy: string;
}

export interface KnowledgeProfile {
  site_display_name: string;
  organization_name: string;
  organization_aliases: string[];
  site_subject: string;
  entity_type: string;
  overview_query_patterns: string[];
  important_topics: ImportantTopic[];
  document_type_rules: Record<string, unknown>[];
  content_hint_rules: Record<string, unknown>[];
  source_priority_rules: Record<string, unknown>[];
  query_expansion_rules: Record<string, unknown>[];
}

export interface KnowledgeProfilePreset {
  id: string;
  label: string;
}

export interface ConfidenceItem {
  value: string;
  confidence: number;
  detail?: string;
  page_count?: number;
  evidence?: string[];
}

export interface GenerationPreview {
  organization?: ConfidenceItem | null;
  website_type?: ConfidenceItem | null;
  website_type_secondary?: ConfidenceItem | null;
  topics: ConfidenceItem[];
  aliases: ConfidenceItem[];
  document_types: ConfidenceItem[];
  overview_patterns: ConfidenceItem[];
  profile?: KnowledgeProfile | null;
  preset_seed?: string;
  low_confidence_keys: string[];
  entities?: ConfidenceItem[];
  content_hints?: ConfidenceItem[];
  warnings?: string[];
  validation_issues?: Record<string, unknown>[];
  analytics?: Record<string, unknown>;
}

export interface ProfileGenerationJobStatus {
  id: number;
  status: string;
  current_stage?: string;
  progress_percent?: number;
  error_message?: string | null;
  preview?: GenerationPreview | null;
  analytics?: Record<string, unknown>;
}

export interface AppliedKnowledgeConfig {
  detected_intent: string;
  matched_topic_key?: string | null;
  matched_topic_label?: string | null;
  matched_aliases: string[];
  query_expansions: string[];
  boosted_document_types: string[];
  deprioritized_document_types: string[];
  boosted_content_hints: string[];
  deprioritized_content_hints: string[];
  supplemental_queries: string[];
}
