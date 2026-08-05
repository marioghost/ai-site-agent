import { describe, expect, it } from "vitest";
import type { AnalyticsInsightsPayload } from "../types";
import { EMPTY_SOURCES, ZERO_RETRIEVAL } from "./performanceAnalytics.fixtures";
import {
  evaluatePerformancePresence,
  hasMeaningfulRetrieval,
  hasMeaningfulSources,
} from "./performanceAnalytics";

describe("performanceAnalytics meaningful gates", () => {
  it("treats zero-filled retrieval as not meaningful", () => {
    expect(hasMeaningfulRetrieval(ZERO_RETRIEVAL)).toBe(false);
    expect(hasMeaningfulRetrieval(null)).toBe(false);
    expect(hasMeaningfulRetrieval({ ...ZERO_RETRIEVAL, avg_chunk_count: 2.1 })).toBe(true);
  });

  it("treats empty source tables as not meaningful", () => {
    expect(hasMeaningfulSources(EMPTY_SOURCES)).toBe(false);
    expect(
      hasMeaningfulSources({
        top_pages: [],
        unused_sources: [{ title: "A", url: "https://a", indexed_at: null, document_type: "page" }],
      })
    ).toBe(true);
  });

  it("evaluatePerformancePresence.isEmpty for zero API objects with no query/trend data", () => {
    expect(
      evaluatePerformancePresence({
        timeseries: [{ bucket_start: "x", requests: 0 } as never],
        popularCount: 0,
        problematicCount: 0,
        retrieval: ZERO_RETRIEVAL,
        sources: EMPTY_SOURCES,
        intents: [],
        topics: [],
        insights: { insights: [], recommendations: [] } as AnalyticsInsightsPayload,
      }).isEmpty
    ).toBe(true);
  });

  it("keeps composition when unused sources are independently useful", () => {
    expect(
      evaluatePerformancePresence({
        timeseries: [],
        popularCount: 0,
        problematicCount: 0,
        retrieval: ZERO_RETRIEVAL,
        sources: {
          top_pages: [],
          unused_sources: [{ title: "A", url: "https://a", indexed_at: null, document_type: "page" }],
        },
        intents: [],
        topics: [],
        insights: null,
      }).isEmpty
    ).toBe(false);
  });
});
