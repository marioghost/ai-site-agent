import { describe, expect, it } from "vitest";
import { PRODUCT_NAV } from "./lib/navConfig";
import { canAccessRoute } from "./lib/permissions";
import appSource from "./App.tsx?raw";
import overviewPageSource from "./pages/OverviewPage.tsx?raw";
import loginPageSource from "./pages/LoginPage.tsx?raw";
import requireAuthSource from "./components/auth/RequireAuth.tsx?raw";
import homeScreenSource from "./features/home/HomeScreen.tsx?raw";
import homeReadinessSource from "./lib/homeReadiness.ts?raw";
import engStatusScreenSource from "./features/engineering/status/EngStatusScreen.tsx?raw";
import engTensionsScreenSource from "./features/engineering/tensions/EngTensionsScreen.tsx?raw";
import performanceScreenSource from "./features/insights/performance/PerformanceScreen.tsx?raw";
import librarySourceScreenSource from "./features/knowledge/library/LibraryScreen.tsx?raw";

describe("S007 Home default + Overview retirement", () => {
  it("makes `/` navigate to `/home` instead of `/overview`", () => {
    const rootRouteMatch = appSource.match(/<Route\s+path="\/"\s+element=\{([^}]+)\}\s*\/>/);
    expect(rootRouteMatch).toBeTruthy();
    expect(rootRouteMatch?.[1]).toMatch(/<Navigate to="\/home" replace \/>/);
    expect(appSource).not.toMatch(/path="\/"\s+element=\{<Navigate to="\/overview"/);
  });

  it("makes the catch-all `*` route navigate to `/home` instead of `/overview`", () => {
    const catchAllMatch = appSource.match(/<Route\s+path="\*"\s+element=\{([^}]+)\}\s*\/>/);
    expect(catchAllMatch).toBeTruthy();
    expect(catchAllMatch?.[1]).toMatch(/<Navigate to="\/home" replace \/>/);
  });

  it("no longer redirects to `/overview` anywhere in App.tsx routing", () => {
    expect(appSource).not.toMatch(/Navigate to="\/overview"/);
    // `/overview` itself remains a registered route (redirect-compatibility shim)
    expect(appSource).toMatch(/path="\/overview"/);
  });

  it("keeps `/home` registered as a real product route", () => {
    expect(appSource).toMatch(/path="\/home"/);
    expect(appSource).toMatch(/HomeScreen/);
  });

  it("turns OverviewPage into a thin redirect wrapper to /home, preserving search/hash", () => {
    expect(overviewPageSource).toMatch(/Navigate/);
    expect(overviewPageSource).toMatch(/pathname: "\/home"/);
    expect(overviewPageSource).toMatch(/search: location\.search/);
    expect(overviewPageSource).toMatch(/hash: location\.hash/);
    expect(overviewPageSource).toMatch(/replace/);
    // No more Overview widget chrome — full product surfaces own this content now
    expect(overviewPageSource).not.toMatch(/AnalyticsPreviewRow/);
    expect(overviewPageSource).not.toMatch(/import KnowledgeBaseStatusCard/);
    expect(overviewPageSource).not.toMatch(/import OverviewKnowledgeOsPanel/);
    expect(overviewPageSource).not.toMatch(/import SubsystemHealthPanel/);
    expect(overviewPageSource).not.toMatch(/import LlmRuntimePanel/);
    expect(overviewPageSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("LoginPage's post-login default destination is `/home`, not `/overview`", () => {
    expect(loginPageSource).toMatch(/\?\.from \?\? "\/home"/);
    expect(loginPageSource).not.toMatch(/\?\.from \?\? "\/overview"/);
  });

  it("RequireAuth's role-mismatch fallback is `/home`, not `/overview`", () => {
    expect(requireAuthSource).toMatch(/roles && !roles\.includes\(user\.role\)[\s\S]*?<Navigate to="\/home" replace \/>/);
    expect(requireAuthSource).not.toMatch(/<Navigate to="\/overview" replace \/>/);
  });

  it("permissions keep `/overview` routable for redirect compatibility", () => {
    expect(canAccessRoute("admin", "/overview")).toBe(true);
    expect(canAccessRoute("operator", "/overview")).toBe(true);
    expect(canAccessRoute("viewer", "/overview")).toBe(true);
  });

  it("Home, not Overview, is the sole top-level product nav landing entry", () => {
    const home = PRODUCT_NAV.find((entry) => entry.kind === "item" && entry.labelKey === "nav.home");
    expect(home).toBeTruthy();
    expect((home as { to?: string })?.to).toBe("/home");

    const overviewEntry = PRODUCT_NAV.find(
      (entry) =>
        (entry.kind === "item" && (entry.to === "/overview" || entry.labelKey === "nav.overview")) ||
        (entry.kind === "section" &&
          entry.items.some((item) => item.to === "/overview" || item.labelKey === "nav.overview"))
    );
    expect(overviewEntry).toBeUndefined();
  });

  it("G6-P2: Performance is the full analytics owner (not a preview fragment)", () => {
    expect(performanceScreenSource).toMatch(/getProductAnalyticsSummary/);
    expect(performanceScreenSource).toMatch(/AnalyticsKpiSection/);
    expect(performanceScreenSource).toMatch(/AnalyticsTrendsSection/);
    expect(performanceScreenSource).not.toMatch(/AnalyticsPreviewRow/);
  });

  it("G6-P2: Library owns knowledge-base readiness detail (ready/waiting/needs_refresh/failed/skipped)", () => {
    expect(librarySourceScreenSource).toMatch(/SourcesSummaryCards/);
    expect(librarySourceScreenSource).toMatch(/SourcesKnowledgeMiniCard/);
    expect(librarySourceScreenSource).toMatch(/knowledgeBase/);
  });

  it("G6-P2: Home shows readiness/quick links to Knowledge, Ask, Performance, Settings", () => {
    expect(homeReadinessSource).toMatch(/\/knowledge\/update/);
    expect(homeReadinessSource).toMatch(/\/knowledge\/library/);
    expect(homeScreenSource).toMatch(/\/ask/);
    expect(homeScreenSource).toMatch(/\/insights\/performance/);
    expect(homeScreenSource).toMatch(/\/settings\/general/);
  });

  it("G6-P2: EngStatusScreen owns subsystem health, LLM runtime panel, and Knowledge OS release/version tags", () => {
    expect(engStatusScreenSource).toMatch(/SubsystemHealthPanel/);
    expect(engStatusScreenSource).toMatch(/LlmRuntimePanel/);
    expect(engStatusScreenSource).toMatch(/overview\.kos\.memory_version/);
    expect(engStatusScreenSource).toMatch(/overview\.kos\.knowledge_version/);
    expect(engStatusScreenSource).toMatch(/eng\.status\.release_tag/);
  });

  it("G6-P2: EngTensionsScreen owns the epistemic tension summary + explorer link", () => {
    expect(engTensionsScreenSource).toMatch(/getEpistemicHealthSummary/);
    expect(engTensionsScreenSource).toMatch(/\/diagnostics\/epistemic-health/);
  });

  it("does not regress S006 Engineering isolation or S005 Home/Ask ownership", () => {
    expect(appSource).toMatch(/path="\/ask"/);
    expect(appSource).toMatch(/path="\/engineering"/);
    expect(appSource).toMatch(/RequireEngineeringMode/);
  });
});
