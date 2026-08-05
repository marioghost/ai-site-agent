import { describe, expect, it } from "vitest";
import type { HealthResponse, KnowledgeBaseStatus, Settings } from "../types";
import {
  computeHomeReadinessState,
  deriveHomeModel,
  healthChecklistCopyKey,
  homeCtasForState,
  isAskReady,
  isHealthOk,
  knowledgeChecklistTone,
  normalizeKnowledgeBuckets,
} from "./homeReadiness";

function kb(partial: Partial<KnowledgeBaseStatus>): KnowledgeBaseStatus {
  return {
    total_sources: 0,
    ready_to_use: 0,
    waiting: 0,
    needs_refresh: 0,
    failed: 0,
    skipped: 0,
    readiness_percent: 0,
    ready_pages: 0,
    ready_files: 0,
    waiting_pages: 0,
    waiting_files: 0,
    chunks_count: 0,
    vectors_count: 0,
    last_indexed_at: null,
    ...partial,
  };
}

function settings(siteUrl: string | null): Settings {
  return { site_url: siteUrl } as Settings;
}

function health(ok: boolean): HealthResponse {
  const status = ok ? "ok" : "error";
  return {
    app: { status },
    database: { status },
    ollama: { status },
    qdrant: { status },
  } as HealthResponse;
}

describe("normalizeKnowledgeBuckets", () => {
  it("excludes skipped from relevant total", () => {
    const buckets = normalizeKnowledgeBuckets(
      kb({ total_sources: 100, ready_to_use: 80, waiting: 0, failed: 0, skipped: 20 })
    );
    expect(buckets.relevantTotal).toBe(80);
    expect(buckets.skipped).toBe(20);
  });

  it("guards nullable / negative values", () => {
    const buckets = normalizeKnowledgeBuckets(
      kb({
        total_sources: -3 as unknown as number,
        ready_to_use: undefined as unknown as number,
        waiting: NaN as unknown as number,
        failed: null as unknown as number,
        skipped: 2,
      })
    );
    expect(buckets.readyToUse).toBe(0);
    expect(buckets.waiting).toBe(0);
    expect(buckets.failed).toBe(0);
    expect(buckets.skipped).toBe(2);
  });
});

describe("computeHomeReadinessState truth table", () => {
  const base = {
    settings: settings("https://example.com"),
    health: health(true),
    job: null,
  };

  it("1. all relevant sources ready → ready", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 10, ready_to_use: 10 }),
      })
    ).toBe("ready");
  });

  it("2. ready + skipped → ready (skipped non-blocking)", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({
          total_sources: 5023,
          ready_to_use: 2910,
          waiting: 0,
          failed: 0,
          skipped: 2113,
          needs_refresh: 0,
        }),
      })
    ).toBe("ready");
  });

  it("3. skipped-only / zero relevant → needs_update", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 50, ready_to_use: 0, skipped: 50 }),
      })
    ).toBe("needs_update");
  });

  it("4. waiting present with ready → needs_attention", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 20, ready_to_use: 15, waiting: 5 }),
      })
    ).toBe("needs_attention");
  });

  it("5. failed present with ready → needs_attention", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 20, ready_to_use: 18, failed: 2 }),
      })
    ).toBe("needs_attention");
  });

  it("6. needs_refresh → needs_attention", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({
          total_sources: 20,
          ready_to_use: 20,
          needs_refresh: 3,
        }),
      })
    ).toBe("needs_attention");
  });

  it("7. partially incomplete relevant (waiting) → needs_attention", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({
          total_sources: 100,
          ready_to_use: 40,
          waiting: 40,
          failed: 0,
          skipped: 20,
        }),
      })
    ).toBe("needs_attention");
  });

  it("8. zero total sources → needs_update", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 0 }),
        sourceCount: 0,
      })
    ).toBe("needs_update");
  });

  it("9. degraded backend → needs_attention", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        health: health(false),
        knowledgeBase: kb({ total_sources: 10, ready_to_use: 10 }),
      })
    ).toBe("needs_attention");
  });

  it("10. no site → needs_setup; running job → updating", () => {
    expect(
      computeHomeReadinessState({
        settings: settings(null),
        health: health(true),
        job: null,
        knowledgeBase: kb({ total_sources: 10, ready_to_use: 10 }),
      })
    ).toBe("needs_setup");

    expect(
      computeHomeReadinessState({
        ...base,
        job: { status: "running" } as never,
        knowledgeBase: kb({ total_sources: 10, ready_to_use: 10 }),
      })
    ).toBe("updating");
  });

  it("ready===0 with waiting → needs_update (not false ready)", () => {
    expect(
      computeHomeReadinessState({
        ...base,
        knowledgeBase: kb({ total_sources: 10, ready_to_use: 0, waiting: 10 }),
      })
    ).toBe("needs_update");
  });
});

describe("CTA / checklist / ask readiness", () => {
  it("deduplicates primary routes across states", () => {
    const ready = homeCtasForState("ready");
    expect(ready.primary.to).toBe("/ask");
    expect(ready.secondary?.to).toBe("/insights/activity");
    expect(ready.secondary?.to).not.toBe(ready.primary.to);

    const attention = homeCtasForState("needs_attention");
    expect(attention.primary.to).toBe("/knowledge/library");
    expect(attention.secondary?.to).toBe("/ask");
  });

  it("knowledge checklist tone matches buckets", () => {
    expect(
      knowledgeChecklistTone(
        normalizeKnowledgeBuckets(kb({ ready_to_use: 10, total_sources: 12, skipped: 2 })),
        false
      )
    ).toBe("ready");
    expect(
      knowledgeChecklistTone(
        normalizeKnowledgeBuckets(kb({ ready_to_use: 8, waiting: 2, total_sources: 10 })),
        false
      )
    ).toBe("attention");
  });

  it("Ask ready only for ready/needs_attention", () => {
    expect(isAskReady("ready")).toBe(true);
    expect(isAskReady("needs_attention")).toBe(true);
    expect(isAskReady("needs_update")).toBe(false);
    expect(isAskReady("needs_setup")).toBe(false);
  });

  it("isHealthOk handles null/partial", () => {
    expect(isHealthOk(null)).toBe(null);
    expect(isHealthOk(health(true))).toBe(true);
    expect(isHealthOk(health(false))).toBe(false);
  });

  it("health checklist copy never calls unknown health degraded", () => {
    expect(healthChecklistCopyKey(true)).toBe("home.checklist.health");
    expect(healthChecklistCopyKey(false)).toBe("home.checklist.health_degraded");
    expect(healthChecklistCopyKey(null)).toBe("home.checklist.health_unknown");
  });

  it("deriveHomeModel returns one consistent pass", () => {
    const model = deriveHomeModel({
      settings: settings("https://example.com"),
      health: health(true),
      job: null,
      knowledgeBase: kb({
        total_sources: 100,
        ready_to_use: 80,
        skipped: 20,
      }),
    });
    expect(model.state).toBe("ready");
    expect(model.buckets.relevantTotal).toBe(80);
    expect(model.primary.to).toBe("/ask");
    expect(model.verdictTone).toBe("ready");
    expect(model.askReady).toBe(true);
  });
});
