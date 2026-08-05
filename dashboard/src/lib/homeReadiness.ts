import type { HealthResponse, IndexJobStatus, KnowledgeBaseStatus, Settings } from "../types";

/** RFC-101 §7 readiness model — single product state for Home. */
export type HomeReadinessState =
  | "needs_setup"
  | "needs_update"
  | "updating"
  | "ready"
  | "needs_attention";

export type HomeCta = { to: string; labelKey: string };

export type HomeKnowledgeBuckets = {
  totalSources: number;
  readyToUse: number;
  waiting: number;
  failed: number;
  skipped: number;
  needsRefresh: number;
  /** Sources that participate in readiness (excludes skipped). */
  relevantTotal: number;
};

export type HomeChecklistTone = "ready" | "attention" | "processing" | "unknown";

export type HomeDerivedModel = {
  state: HomeReadinessState;
  buckets: HomeKnowledgeBuckets;
  primary: HomeCta;
  secondary: HomeCta | null;
  healthOk: boolean | null;
  askReady: boolean;
  knowledgeTone: HomeChecklistTone;
  healthTone: HomeChecklistTone;
  askTone: HomeChecklistTone;
  siteTone: HomeChecklistTone;
  verdictTone: HomeChecklistTone;
};

function nonNeg(n: number | null | undefined): number {
  if (n == null || Number.isNaN(n)) return 0;
  return Math.max(0, Math.floor(n));
}

export function isHealthOk(health: HealthResponse | null): boolean | null {
  if (!health) return null;
  const statuses = [health.app?.status, health.database?.status, health.ollama?.status, health.qdrant?.status];
  if (statuses.some((s) => s == null || String(s).trim() === "")) return null;
  return statuses.every((status) => String(status).toLowerCase() === "ok");
}

/**
 * Normalize KB counters to match backend readiness semantics:
 * skipped sources are excluded from the relevant total.
 */
export function normalizeKnowledgeBuckets(
  knowledgeBase: KnowledgeBaseStatus | null,
  sourceCountFallback = 0
): HomeKnowledgeBuckets {
  const readyToUse = nonNeg(knowledgeBase?.ready_to_use);
  const waiting = nonNeg(knowledgeBase?.waiting);
  const failed = nonNeg(knowledgeBase?.failed);
  const skipped = nonNeg(knowledgeBase?.skipped);
  const needsRefresh = nonNeg(knowledgeBase?.needs_refresh);
  const totalFromKb = knowledgeBase?.total_sources;
  const totalSources =
    totalFromKb == null || Number.isNaN(totalFromKb)
      ? nonNeg(sourceCountFallback)
      : nonNeg(totalFromKb);

  const summedRelevant = readyToUse + waiting + failed;
  const relevantTotal =
    summedRelevant > 0 || skipped > 0 || totalSources === 0
      ? summedRelevant
      : Math.max(0, totalSources - skipped);

  return {
    totalSources,
    readyToUse,
    waiting,
    failed,
    skipped,
    needsRefresh,
    relevantTotal,
  };
}

export function computeHomeReadinessState(params: {
  settings: Settings | null;
  health: HealthResponse | null;
  job: IndexJobStatus | null;
  knowledgeBase: KnowledgeBaseStatus | null;
  sourceCount?: number;
  /** Optional precomputed buckets to avoid double normalization. */
  buckets?: HomeKnowledgeBuckets;
}): HomeReadinessState {
  const { settings, health, job, knowledgeBase, sourceCount = 0 } = params;

  if (!settings?.site_url) return "needs_setup";
  if (job?.status === "running") return "updating";

  const buckets = params.buckets ?? normalizeKnowledgeBuckets(knowledgeBase, sourceCount);
  const { readyToUse, waiting, failed, needsRefresh, relevantTotal } = buckets;

  if (relevantTotal === 0 || readyToUse === 0) return "needs_update";

  const healthOk = isHealthOk(health);
  if (healthOk === false || failed > 0 || waiting > 0 || needsRefresh > 0) {
    return "needs_attention";
  }

  return "ready";
}

/** RFC-101 §7 — at most one primary CTA and one secondary CTA. */
export function homeCtasForState(state: HomeReadinessState): {
  primary: HomeCta;
  secondary: HomeCta | null;
} {
  switch (state) {
    case "needs_setup":
      return { primary: { to: "/knowledge/site", labelKey: "home.action.go_site" }, secondary: null };
    case "needs_update":
      return {
        primary: { to: "/knowledge/update", labelKey: "home.action.update_knowledge" },
        secondary: null,
      };
    case "updating":
      return { primary: { to: "/knowledge/update", labelKey: "home.action.view_progress" }, secondary: null };
    case "needs_attention":
      return {
        primary: { to: "/knowledge/library", labelKey: "home.action.review_library" },
        secondary: { to: "/ask", labelKey: "home.action.ask" },
      };
    case "ready":
      return {
        primary: { to: "/ask", labelKey: "home.action.ask" },
        secondary: { to: "/insights/activity", labelKey: "home.action.view_activity" },
      };
  }
}

export function knowledgeChecklistTone(
  buckets: HomeKnowledgeBuckets,
  jobRunning: boolean
): HomeChecklistTone {
  if (buckets.relevantTotal === 0 || buckets.readyToUse === 0) {
    return jobRunning ? "processing" : "attention";
  }
  if (buckets.failed > 0 || buckets.waiting > 0 || buckets.needsRefresh > 0) {
    return "attention";
  }
  return "ready";
}

export function isAskReady(state: HomeReadinessState): boolean {
  return state === "ready" || state === "needs_attention";
}

export function healthToneFromOk(healthOk: boolean | null): HomeChecklistTone {
  if (healthOk === null) return "unknown";
  return healthOk ? "ready" : "attention";
}

export function verdictToneFromState(state: HomeReadinessState): HomeChecklistTone {
  if (state === "ready") return "ready";
  if (state === "updating") return "processing";
  return "attention";
}

/** Checklist copy must match health tone — never call unknown health “degraded”. */
export function healthChecklistCopyKey(healthOk: boolean | null): string {
  if (healthOk === true) return "home.checklist.health";
  if (healthOk === false) return "home.checklist.health_degraded";
  return "home.checklist.health_unknown";
}

/** Single derivation pass for Home — avoids double bucket normalization. */
export function deriveHomeModel(params: {
  settings: Settings | null;
  health: HealthResponse | null;
  job: IndexJobStatus | null;
  knowledgeBase: KnowledgeBaseStatus | null;
  sourceCount?: number;
}): HomeDerivedModel {
  const buckets = normalizeKnowledgeBuckets(params.knowledgeBase, params.sourceCount ?? 0);
  const state = computeHomeReadinessState({ ...params, buckets });
  const { primary, secondary } = homeCtasForState(state);
  const healthOk = isHealthOk(params.health);
  const askReady = isAskReady(state);

  return {
    state,
    buckets,
    primary,
    secondary,
    healthOk,
    askReady,
    knowledgeTone: knowledgeChecklistTone(buckets, params.job?.status === "running"),
    healthTone: healthToneFromOk(healthOk),
    askTone: askReady ? "ready" : "attention",
    siteTone: params.settings?.site_url ? "ready" : "attention",
    verdictTone: verdictToneFromState(state),
  };
}
