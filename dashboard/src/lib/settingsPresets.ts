import type { Settings } from "../types";

export type AgentPreset = "automatic" | "fast" | "balanced" | "high_precision";

const RETRIEVAL_KEYS: (keyof Settings)[] = [
  "retrieval_profile",
  "retrieval_mode",
  "top_k",
  "similarity_threshold",
  "retrieval_candidate_count",
  "max_pages_in_context",
  "max_chunks_per_page",
  "max_sources_in_prompt",
  "top_k_dense",
  "top_k_lexical",
  "rerank_limit",
  "document_limit",
  "minimum_retrieval_score",
  "enable_intent_aware_retrieval",
  "enable_source_intelligence",
  "enable_reranking",
  "enable_query_expansion",
  "enable_broad_question_mode",
  "enable_context_builder",
  "llm_mode_profile",
  "fast_mode_enabled",
];

export function deriveAgentPreset(settings: Settings): AgentPreset {
  const profile = (settings.retrieval_profile ?? "automatic").toLowerCase();
  if (profile === "high_precision" || settings.llm_mode_profile === "high_quality") {
    return "high_precision";
  }
  if (profile === "fast" || settings.llm_mode_profile === "fast") {
    return "fast";
  }
  if (profile === "balanced") {
    return "balanced";
  }
  return "automatic";
}

export function applyAgentPreset(settings: Settings, preset: AgentPreset): Settings {
  const next = {
    ...settings,
    enable_query_expansion: true,
    retrieval_mode: "hybrid" as const,
    enable_intent_aware_retrieval: true,
    enable_source_intelligence: true,
    enable_reranking: true,
    enable_context_builder: true,
    enable_broad_question_mode: true,
    homepage_boost_enabled: true,
    document_priorities_json: "",
    intent_profiles_json: "",
    scoring_weights_json: "",
  };

  if (preset === "fast") {
    next.llm_mode_profile = "fast";
    next.retrieval_profile = "fast";
    next.fast_mode_enabled = true;
    next.max_sources_in_prompt = 2;
    next.top_k = 4;
    next.max_pages_in_context = 2;
  } else if (preset === "high_precision") {
    next.llm_mode_profile = "high_quality";
    next.retrieval_profile = "high_precision";
    next.fast_mode_enabled = false;
    next.max_sources_in_prompt = 3;
    next.top_k = 5;
    next.max_pages_in_context = 3;
  } else if (preset === "balanced") {
    next.llm_mode_profile = "balanced";
    next.retrieval_profile = "balanced";
    next.fast_mode_enabled = false;
    next.max_sources_in_prompt = 3;
    next.top_k = 5;
    next.max_pages_in_context = 3;
  } else {
    next.llm_mode_profile = "balanced";
    next.retrieval_profile = "automatic";
    next.fast_mode_enabled = false;
    next.max_sources_in_prompt = 3;
    next.top_k = 5;
    next.max_pages_in_context = 3;
  }
  return next;
}

export function applySmartSearch(settings: Settings, enabled: boolean): Settings {
  return {
    ...settings,
    enable_intent_aware_retrieval: enabled,
    enable_source_intelligence: enabled,
    enable_broad_question_mode: enabled,
    enable_canonical_source_selection: enabled,
    enable_reranking: enabled,
    enable_context_builder: enabled,
    enable_query_expansion: enabled,
    retrieval_mode: "hybrid",
  };
}

export function isSmartSearchEnabled(settings: Settings): boolean {
  return (
    (settings.enable_intent_aware_retrieval ?? true) &&
    (settings.enable_source_intelligence ?? true)
  );
}

export function retrievalSettingsChanged(before: Settings, after: Settings): boolean {
  return RETRIEVAL_KEYS.some((key) => before[key] !== after[key]);
}
