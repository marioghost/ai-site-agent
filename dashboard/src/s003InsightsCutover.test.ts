import { describe, expect, it } from "vitest";
import { PRODUCT_NAV } from "./lib/navConfig";
import appSource from "./App.tsx?raw";
import analyticsPageSource from "./pages/AnalyticsPage.tsx?raw";
import logsPageSource from "./pages/LogsPage.tsx?raw";
import insightsLayoutSource from "./layouts/InsightsLayout.tsx?raw";
import performanceScreenSource from "./features/insights/performance/PerformanceScreen.tsx?raw";
import activityScreenSource from "./features/insights/activity/ActivityScreen.tsx?raw";

describe("S003 Insights product cutover", () => {
  it("keeps canonical Insights owners in product nav", () => {
    const insights = PRODUCT_NAV.find((entry) => entry.kind === "section" && entry.labelKey === "nav.insights");
    expect(insights).toBeTruthy();
    if (!insights || insights.kind !== "section") {
      throw new Error("insights nav section missing");
    }
    expect(insights.items.map((item) => item.to)).toEqual([
      "/insights/performance",
      "/insights/activity",
    ]);
    expect(insights.items.some((item) => item.to === "/analytics")).toBe(false);
    expect(insights.items.some((item) => item.to === "/logs")).toBe(false);
  });

  it("registers canonical Insights routes", () => {
    expect(appSource).toMatch(/path="performance"/);
    expect(appSource).toMatch(/path="activity"/);
  });

  it("keeps legacy Insights routes only as redirects", () => {
    expect(analyticsPageSource).toMatch(/Navigate/);
    expect(analyticsPageSource).not.toMatch(/AnalyticsKpiSection|getProductAnalyticsSummary/);
    expect(analyticsPageSource).toMatch(/\/insights\/performance/);
    expect(logsPageSource).toMatch(/Navigate/);
    expect(logsPageSource).not.toMatch(/getChatLogs|DataTable/);
    expect(logsPageSource).toMatch(/\/insights\/activity/);
  });

  it("removes S001 placeholders from canonical Insights screens", () => {
    expect(performanceScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(activityScreenSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("adds InsightsLayout section navigation for canonical owners", () => {
    expect(insightsLayoutSource).toMatch(/\/insights\/performance/);
    expect(insightsLayoutSource).toMatch(/\/insights\/activity/);
  });

  it("migrates owner implementation into Insights feature modules", () => {
    expect(performanceScreenSource).toMatch(/AnalyticsKpiSection|PopularQueriesSection/);
    expect(activityScreenSource).toMatch(/getChatLogs/);
    expect(performanceScreenSource).not.toMatch(/components\/analytics/);
    expect(activityScreenSource).not.toMatch(/pages\/LogsPage/);
  });

  it("does not regress Knowledge product nav owners from S002", () => {
    const knowledge = PRODUCT_NAV.find((entry) => entry.kind === "section" && entry.labelKey === "nav.knowledge");
    expect(knowledge).toBeTruthy();
    if (!knowledge || knowledge.kind !== "section") {
      throw new Error("knowledge nav section missing");
    }
    expect(knowledge.items.map((item) => item.to)).toEqual([
      "/knowledge/library",
      "/knowledge/update",
      "/knowledge/site",
    ]);
  });
});
