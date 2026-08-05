import { describe, expect, it } from "vitest";
import { PRODUCT_NAV } from "./lib/navConfig";
import { canAccessRoute } from "./lib/permissions";
import appSource from "./App.tsx?raw";
import chatTestPageSource from "./pages/ChatTestPage.tsx?raw";
import homeScreenSource from "./features/home/HomeScreen.tsx?raw";
import askScreenSource from "./features/ask/AskScreen.tsx?raw";
import overviewPageSource from "./pages/OverviewPage.tsx?raw";
import performanceWidgetSource from "./features/insights/performance/widgets/ProblematicQueriesSection.tsx?raw";
import analyticsWidgetSource from "./components/analytics/ProblematicQueriesSection.tsx?raw";

describe("S005 Home shell + Ask coexistence", () => {
  it("removes the S001 MigrationPlaceholder from Home and Ask", () => {
    expect(homeScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(askScreenSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("gives Home a real readiness shell (PageHeader, CTAs, loading/error states)", () => {
    expect(homeScreenSource).toMatch(/PageHeader/);
    expect(homeScreenSource).toMatch(/LoadingState/);
    expect(homeScreenSource).toMatch(/ErrorState/);
    // Readiness model per RFC-101 §7
    expect(homeScreenSource).toMatch(/needs_setup/);
    expect(homeScreenSource).toMatch(/needs_update/);
    expect(homeScreenSource).toMatch(/updating/);
    expect(homeScreenSource).toMatch(/ready/);
    expect(homeScreenSource).toMatch(/needs_attention/);
    // Uses existing lightweight APIs, not the full Overview widget set
    expect(homeScreenSource).toMatch(/getHealth/);
    expect(homeScreenSource).toMatch(/getOverview/);
    expect(homeScreenSource).toMatch(/getIndexStatus/);
    expect(homeScreenSource).toMatch(/listSources/);
    expect(homeScreenSource).toMatch(/getSettings/);
    expect(homeScreenSource).not.toMatch(/getAnalyticsSummary|getAnalyticsTimeseries|getIntentDistribution|AnalyticsPreviewRow/);
    // Primary CTA destinations appropriate to readiness state
    expect(homeScreenSource).toMatch(/\/ask/);
    expect(homeScreenSource).toMatch(/\/knowledge\/update/);
    expect(homeScreenSource).toMatch(/\/insights\/performance/);
    expect(homeScreenSource).toMatch(/\/settings\/general/);
  });

  it("keeps `/` and Overview redirect wiring stable pre-S007 (S007 retires Overview as default; see s007HomeDefaultOverview.test.ts for the current contract)", () => {
    expect(overviewPageSource).not.toMatch(/MigrationPlaceholder/);
    expect(appSource).toMatch(/path="\/overview"/);
  });

  it("migrates the Chat Test product chrome into Ask", () => {
    expect(askScreenSource).toMatch(/useChatSession/);
    expect(askScreenSource).toMatch(/ChatToolbar/);
    expect(askScreenSource).toMatch(/ChatMessageList/);
    expect(askScreenSource).toMatch(/ChatComposer/);
    // S006 (G3-P2/P3) retired history/diagnostics chrome from Ask — see
    // s006EngineeringIsolation.test.ts for the current contract.
    expect(askScreenSource).not.toMatch(/pages\/ChatTestPage/);
  });

  it("uses an ask-oriented product title", () => {
    expect(askScreenSource).toMatch(/nav\.ask|ask\.title/);
  });

  it("keeps legacy `/chat` as a redirect wrapper preserving search/hash", () => {
    expect(chatTestPageSource).toMatch(/Navigate/);
    expect(chatTestPageSource).not.toMatch(/useChatSession|ChatToolbar|ChatMessageList/);
    expect(chatTestPageSource).toMatch(/\/ask/);
    expect(chatTestPageSource).toMatch(/search/);
    expect(chatTestPageSource).toMatch(/hash/);
  });

  it("registers canonical Home and Ask routes alongside a working /chat redirect", () => {
    expect(appSource).toMatch(/path="\/home"/);
    expect(appSource).toMatch(/path="\/ask"/);
    expect(appSource).toMatch(/path="\/chat"/);
  });

  it("keeps Home top-level and Ask top-level in product nav", () => {
    const home = PRODUCT_NAV.find((entry) => entry.kind === "item" && entry.labelKey === "nav.home");
    expect(home).toBeTruthy();
    expect((home as { to?: string })?.to).toBe("/home");

    const ask = PRODUCT_NAV.find((entry) => entry.kind === "item" && entry.labelKey === "nav.ask");
    expect(ask).toBeTruthy();
    expect((ask as { to?: string })?.to).toBe("/ask");
  });

  it("enforces /ask and /chat as admin/operator only, and /home as broadly readable", () => {
    expect(canAccessRoute("admin", "/ask")).toBe(true);
    expect(canAccessRoute("operator", "/ask")).toBe(true);
    expect(canAccessRoute("viewer", "/ask")).toBe(false);

    expect(canAccessRoute("admin", "/chat")).toBe(true);
    expect(canAccessRoute("operator", "/chat")).toBe(true);
    expect(canAccessRoute("viewer", "/chat")).toBe(false);

    expect(canAccessRoute("admin", "/home")).toBe(true);
    expect(canAccessRoute("operator", "/home")).toBe(true);
    expect(canAccessRoute("viewer", "/home")).toBe(true);
  });

  it("actually gates /ask and /chat behind the admin/operator RequireAuth wrapper in App.tsx", () => {
    const chatGuardMatch = appSource.match(
      /<Route element=\{<RequireAuth roles=\{\["admin", "operator"\]\} \/>\}>([\s\S]*?)<\/Route>/
    );
    expect(chatGuardMatch).toBeTruthy();
    const guardedBlock = chatGuardMatch?.[1] ?? "";
    expect(guardedBlock).toMatch(/path="\/chat"/);
    expect(guardedBlock).toMatch(/path="\/ask"/);
  });

  it("retargets ProblematicQueries deep links from /chat to /ask", () => {
    expect(performanceWidgetSource).toMatch(/\/ask\?q=/);
    expect(performanceWidgetSource).not.toMatch(/\/chat\?q=/);
    expect(analyticsWidgetSource).toMatch(/\/ask\?q=/);
    expect(analyticsWidgetSource).not.toMatch(/\/chat\?q=/);
  });

  it("keeps Home and Ask ownership under features/home and features/ask (RFC-102, G8-P2)", () => {
    expect(homeScreenSource).not.toMatch(/components\/overview/);
    expect(askScreenSource).not.toMatch(/pages\/ChatTestPage/);
    // Ask reuses the shared chat feature components/context (not a fork)
    expect(askScreenSource).toMatch(/\.\.\/\.\.\/components\/chat\//);
    expect(askScreenSource).toMatch(/\.\.\/\.\.\/context\/ChatSessionContext/);
  });

  it("does not regress Settings ownership from S004", () => {
    const settings = PRODUCT_NAV.find(
      (entry) => entry.kind === "section" && entry.labelKey === "nav.settings"
    );
    expect(settings).toBeTruthy();
    if (!settings || settings.kind !== "section") {
      throw new Error("settings nav section missing");
    }
    expect(settings.items.map((item) => item.to)).toEqual([
      "/settings/general",
      "/settings/models",
      "/settings/answers",
      "/settings/access",
    ]);
  });
});
