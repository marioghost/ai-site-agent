/** Retrieval mode limits aligned with backend `retrieval_engine/config.py`. */

export type RetrievalProfileName =
  | "automatic"
  | "fast"
  | "balanced"
  | "high_precision"
  | "high_recall"
  | "enterprise";

export interface RetrievalProfileLimits {
  top_k_dense: number;
  top_k_lexical: number;
  rerank_limit: number;
  context_limit: number;
  document_limit: number;
  chunk_limit: number;
  minimum_score: number;
}

export const RETRIEVAL_PROFILES: Record<RetrievalProfileName, RetrievalProfileLimits> = {
  automatic: {
    top_k_dense: 35,
    top_k_lexical: 35,
    rerank_limit: 18,
    context_limit: 3,
    document_limit: 3,
    chunk_limit: 2,
    minimum_score: 0.36,
  },
  fast: {
    top_k_dense: 15,
    top_k_lexical: 15,
    rerank_limit: 8,
    context_limit: 2,
    document_limit: 2,
    chunk_limit: 1,
    minimum_score: 0.4,
  },
  balanced: {
    top_k_dense: 30,
    top_k_lexical: 30,
    rerank_limit: 15,
    context_limit: 3,
    document_limit: 3,
    chunk_limit: 2,
    minimum_score: 0.35,
  },
  high_precision: {
    top_k_dense: 25,
    top_k_lexical: 25,
    rerank_limit: 10,
    context_limit: 2,
    document_limit: 2,
    chunk_limit: 1,
    minimum_score: 0.5,
  },
  high_recall: {
    top_k_dense: 50,
    top_k_lexical: 50,
    rerank_limit: 25,
    context_limit: 5,
    document_limit: 5,
    chunk_limit: 3,
    minimum_score: 0.25,
  },
  enterprise: {
    top_k_dense: 40,
    top_k_lexical: 40,
    rerank_limit: 20,
    context_limit: 4,
    document_limit: 4,
    chunk_limit: 2,
    minimum_score: 0.38,
  },
};

export function parseJsonRecord(raw: string | null | undefined): Record<string, number> | null {
  if (!raw?.trim()) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) return null;
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(parsed)) {
      const n = Number(v);
      if (!Number.isNaN(n)) out[k] = n;
    }
    return out;
  } catch {
    return null;
  }
}

export function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
