/** Pure helpers for Understanding / Epistemic Health tensions panel (Step 036+). */

import type { ProvenanceScope } from "../types";

export type TensionFilter = "all" | "support_deficit" | "conflict";

export type TensionLike = {
  tension_type: string;
  claim_ids: number[];
  observation_ref_ids: number[];
  evidence_link_ids: number[];
  summary: string;
  provenance_scope?: string;
  claim_provenance_kinds?: string[];
  is_test_data?: boolean;
};

export type TensionCounts = {
  total: number;
  support_deficit: number;
  conflict: number;
};

/** Format provenance ID lists for the Understanding tensions table. */
export function formatIdList(ids: number[] | undefined | null): string {
  if (!ids || ids.length === 0) return "—";
  return ids.join(", ");
}

export function tensionRowKey(item: TensionLike): string {
  return [
    item.tension_type,
    item.claim_ids.join("-"),
    item.observation_ref_ids.join("-"),
    item.evidence_link_ids.join("-"),
    item.provenance_scope ?? "",
    item.is_test_data ? "test" : "real",
  ].join("|");
}

export function countTensions(items: TensionLike[]): TensionCounts {
  let support_deficit = 0;
  let conflict = 0;
  for (const item of items) {
    if (item.tension_type === "support_deficit") support_deficit += 1;
    else if (item.tension_type === "conflict") conflict += 1;
  }
  return { total: items.length, support_deficit, conflict };
}

export function filterTensions(
  items: TensionLike[],
  filter: TensionFilter
): TensionLike[] {
  if (filter === "all") return items;
  return items.filter((item) => item.tension_type === filter);
}

export function paginateTensions<T>(
  items: T[],
  page: number,
  pageSize: number
): { items: T[]; total: number; page: number; pageSize: number; totalPages: number } {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1);
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    total,
    page: safePage,
    pageSize,
    totalPages,
  };
}

/** API-shaped diagnostic payload — no ORM fields. */
export function tensionDiagnosticJson(item: TensionLike): string {
  return JSON.stringify(
    {
      tension_type: item.tension_type,
      claim_ids: item.claim_ids,
      observation_ref_ids: item.observation_ref_ids,
      evidence_link_ids: item.evidence_link_ids,
      summary: item.summary,
      provenance_scope: item.provenance_scope ?? null,
      claim_provenance_kinds: item.claim_provenance_kinds ?? [],
      is_test_data: item.is_test_data ?? false,
    },
    null,
    2
  );
}

export type ListTensionsPage = {
  items: TensionLike[];
  total: number;
  page: number;
  page_size: number;
  provenance_scope?: ProvenanceScope;
};

/** Fetch all pages from the Step 035 API contract (max page_size 200). */
export async function fetchAllTensions(
  listFn: (params: {
    page: number;
    page_size: number;
    provenance_scope?: ProvenanceScope;
  }) => Promise<ListTensionsPage>,
  pageSize = 200,
  provenance_scope: ProvenanceScope = "real"
): Promise<TensionLike[]> {
  const all: TensionLike[] = [];
  let page = 1;
  let total = Infinity;
  while (all.length < total) {
    const res = await listFn({ page, page_size: pageSize, provenance_scope });
    total = res.total;
    all.push(...res.items);
    if (res.items.length === 0 || all.length >= total) break;
    page += 1;
    if (page > 1000) break;
  }
  return all;
}

/** Banned control labels / actions for this read-only surface. */
export const UNDERSTANDING_WRITE_ACTION_TOKENS = [
  "resolve",
  "investigate",
  "classify",
  "delete tension",
  "edit tension",
  "persist",
] as const;

export type UnderstandingViewState = "loading" | "error" | "empty" | "ready";

export function resolveUnderstandingViewState(input: {
  loading: boolean;
  error: string | null;
  itemCount: number;
}): UnderstandingViewState {
  if (input.loading && input.itemCount === 0) return "loading";
  if (input.error && input.itemCount === 0) return "error";
  if (input.itemCount === 0) return "empty";
  return "ready";
}
