/**
 * S008 — Structure polish, cleanup, validation, Product Readiness evidence.
 *
 * Program: docs/releases/1.0-rfc-101-master-program.md
 * Package IDs: G8-P3, G8-P4, G9-P2, G9-P3
 * Inventory findings: A1.2, A17.2, A9.2, A15.1
 * Execution Strategy: docs/releases/1.0-rfc-101-execution-strategy.md
 *
 * This suite is a **final route-model contract** snapshot for the whole
 * S001–S007 cutover: it does not implement anything new (all assertions
 * below already held true after S007 — see docs/releases/S008-*.md for the
 * verification evidence), it locks the accepted end state so a future
 * change cannot silently regress ownership, redirects, or Engineering
 * isolation without failing a test.
 */
import { describe, expect, it } from "vitest";
import { PRODUCT_NAV, ENGINEERING_NAV } from "./lib/navConfig";
import appSource from "./App.tsx?raw";
import overviewPageSource from "./pages/OverviewPage.tsx?raw";
import chatTestPageSource from "./pages/ChatTestPage.tsx?raw";
import usersPageSource from "./pages/UsersPage.tsx?raw";
import analyticsPageSource from "./pages/AnalyticsPage.tsx?raw";
import logsPageSource from "./pages/LogsPage.tsx?raw";
import sourcesPageSource from "./pages/SourcesPage.tsx?raw";
import indexingPageSource from "./pages/IndexingPage.tsx?raw";
import knowledgeProfilePageSource from "./pages/KnowledgeProfilePage.tsx?raw";
import homeScreenSource from "./features/home/HomeScreen.tsx?raw";
import askScreenSource from "./features/ask/AskScreen.tsx?raw";
import performanceScreenSource from "./features/insights/performance/PerformanceScreen.tsx?raw";
import activityScreenSource from "./features/insights/activity/ActivityScreen.tsx?raw";
import generalScreenSource from "./features/settings/general/GeneralScreen.tsx?raw";
import modelsScreenSource from "./features/settings/models/ModelsScreen.tsx?raw";
import answersScreenSource from "./features/settings/answers/AnswersScreen.tsx?raw";
import accessScreenSource from "./features/settings/access/AccessScreen.tsx?raw";
import engStatusScreenSource from "./features/engineering/status/EngStatusScreen.tsx?raw";
import engKnowledgeScreenSource from "./features/engineering/knowledge/EngKnowledgeScreen.tsx?raw";
import engTensionsScreenSource from "./features/engineering/tensions/EngTensionsScreen.tsx?raw";
import engAdvancedScreenSource from "./features/engineering/advanced/EngAdvancedScreen.tsx?raw";
import engBuildScreenSource from "./features/engineering/build/EngBuildScreen.tsx?raw";
import engineeringLayoutSource from "./layouts/EngineeringLayout.tsx?raw";
import libraryScreenSource from "./features/knowledge/library/LibraryScreen.tsx?raw";
import updateScreenSource from "./features/knowledge/update/UpdateScreen.tsx?raw";
import siteScreenSource from "./features/knowledge/site/SiteScreen.tsx?raw";

describe("S008 Product Completion — final route model contracts", () => {
  describe("root + legacy redirects", () => {
    it("`/` redirects to /home", () => {
      const rootRouteMatch = appSource.match(/<Route\s+path="\/"\s+element=\{([^}]+)\}\s*\/>/);
      expect(rootRouteMatch).toBeTruthy();
      expect(rootRouteMatch?.[1]).toMatch(/<Navigate to="\/home" replace \/>/);
    });

    it("catch-all `*` redirects to /home", () => {
      const catchAllMatch = appSource.match(/<Route\s+path="\*"\s+element=\{([^}]+)\}\s*\/>/);
      expect(catchAllMatch).toBeTruthy();
      expect(catchAllMatch?.[1]).toMatch(/<Navigate to="\/home" replace \/>/);
    });

    it("Overview (/overview) is a redirect-only compatibility shim to /home", () => {
      expect(overviewPageSource).toMatch(/Navigate/);
      expect(overviewPageSource).toMatch(/pathname: "\/home"/);
      expect(overviewPageSource).not.toMatch(/MigrationPlaceholder/);
    });

    it("Chat (/chat) redirects to /ask", () => {
      expect(chatTestPageSource).toMatch(/Navigate/);
      expect(chatTestPageSource).toMatch(/pathname: "\/ask"/);
    });

    it("Users (/users) redirects to /settings/access", () => {
      expect(usersPageSource).toMatch(/Navigate/);
      expect(usersPageSource).toMatch(/pathname: "\/settings\/access"/);
    });

    it("Analytics (/analytics) and Logs (/logs) redirect into Insights", () => {
      expect(analyticsPageSource).toMatch(/Navigate/);
      expect(analyticsPageSource).toMatch(/pathname: "\/insights\/performance"/);
      expect(logsPageSource).toMatch(/Navigate/);
      expect(logsPageSource).toMatch(/pathname: "\/insights\/activity"/);
    });

    it("Sources/Indexing/Knowledge Profile redirect into Knowledge", () => {
      expect(sourcesPageSource).toMatch(/Navigate/);
      expect(sourcesPageSource).toMatch(/pathname: "\/knowledge\/library"/);
      expect(indexingPageSource).toMatch(/Navigate/);
      expect(indexingPageSource).toMatch(/pathname: "\/knowledge\/update"/);
      expect(knowledgeProfilePageSource).toMatch(/Navigate/);
      expect(knowledgeProfilePageSource).toMatch(/pathname: "\/knowledge\/site"/);
    });

    it("every legacy redirect page preserves search and hash", () => {
      for (const source of [
        overviewPageSource,
        chatTestPageSource,
        usersPageSource,
        analyticsPageSource,
        logsPageSource,
        sourcesPageSource,
        indexingPageSource,
        knowledgeProfilePageSource,
      ]) {
        expect(source).toMatch(/search: location\.search/);
        expect(source).toMatch(/hash: location\.hash/);
        expect(source).toMatch(/replace/);
      }
    });
  });

  describe("PRODUCT_NAV shape (Mode off)", () => {
    it("has exactly Home, Knowledge trio, Ask, Insights duo, Settings quartet — no legacy owners", () => {
      const home = PRODUCT_NAV.find((entry) => entry.kind === "item" && entry.labelKey === "nav.home");
      expect(home).toBeTruthy();
      expect((home as { to?: string })?.to).toBe("/home");

      const ask = PRODUCT_NAV.find((entry) => entry.kind === "item" && entry.labelKey === "nav.ask");
      expect(ask).toBeTruthy();
      expect((ask as { to?: string })?.to).toBe("/ask");

      const knowledge = PRODUCT_NAV.find(
        (entry) => entry.kind === "section" && entry.labelKey === "nav.knowledge"
      );
      expect(knowledge).toBeTruthy();
      if (!knowledge || knowledge.kind !== "section") throw new Error("knowledge nav section missing");
      expect(knowledge.items.map((item) => item.to)).toEqual([
        "/knowledge/library",
        "/knowledge/update",
        "/knowledge/site",
      ]);

      const insights = PRODUCT_NAV.find(
        (entry) => entry.kind === "section" && entry.labelKey === "nav.insights"
      );
      expect(insights).toBeTruthy();
      if (!insights || insights.kind !== "section") throw new Error("insights nav section missing");
      expect(insights.items.map((item) => item.to)).toEqual([
        "/insights/performance",
        "/insights/activity",
      ]);

      const settings = PRODUCT_NAV.find(
        (entry) => entry.kind === "section" && entry.labelKey === "nav.settings"
      );
      expect(settings).toBeTruthy();
      if (!settings || settings.kind !== "section") throw new Error("settings nav section missing");
      expect(settings.items.map((item) => item.to)).toEqual([
        "/settings/general",
        "/settings/models",
        "/settings/answers",
        "/settings/access",
      ]);

      expect(PRODUCT_NAV.length).toBe(5);
    });

    it("does not list Overview, Analytics, Logs, Users, or Sources as top-level or nested nav owners", () => {
      const forbiddenPaths = ["/overview", "/analytics", "/logs", "/users", "/sources", "/indexing", "/knowledge-profile", "/chat"];
      for (const entry of PRODUCT_NAV) {
        if (entry.kind === "item") {
          expect(forbiddenPaths).not.toContain(entry.to);
        } else {
          for (const item of entry.items) {
            expect(forbiddenPaths).not.toContain(item.to);
          }
        }
      }
    });
  });

  describe("no MigrationPlaceholder on any canonical owner screen", () => {
    it("Home, Ask, Performance, Activity own real content (no placeholder)", () => {
      expect(homeScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(askScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(performanceScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(activityScreenSource).not.toMatch(/MigrationPlaceholder/);
    });

    it("Settings owners (General/Models/Answers/Access) own real content (no placeholder)", () => {
      expect(generalScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(modelsScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(answersScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(accessScreenSource).not.toMatch(/MigrationPlaceholder/);
    });

    it("Engineering owners own real content (no placeholder)", () => {
      expect(engStatusScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(engKnowledgeScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(engTensionsScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(engAdvancedScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(engBuildScreenSource).not.toMatch(/MigrationPlaceholder/);
    });

    it("Knowledge owners (Library/Update/Site) own real content (no placeholder)", () => {
      expect(libraryScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(updateScreenSource).not.toMatch(/MigrationPlaceholder/);
      expect(siteScreenSource).not.toMatch(/MigrationPlaceholder/);
    });
  });

  describe("Engineering isolation structure", () => {
    it("EngineeringLayout renders section nav for Engineering destinations (no Chat details)", () => {
      expect(ENGINEERING_NAV.items.map((item) => item.to)).toEqual([
        "/engineering/status",
        "/engineering/knowledge",
        "/engineering/tensions",
        "/engineering/advanced",
        "/engineering/build",
      ]);
      expect(engineeringLayoutSource).toMatch(/ENGINEERING_NAV/);
      expect(engineeringLayoutSource).toMatch(/Outlet/);
    });

    it("App.tsx registers Engineering routes behind RequireEngineeringMode; ask-details redirects to Ask", () => {
      expect(appSource).toMatch(/RequireEngineeringMode/);
      expect(appSource).toMatch(/path="status"/);
      expect(appSource).toMatch(/path="ask-details"/);
      expect(appSource).toMatch(/Navigate to="\/ask"/);
      expect(appSource).toMatch(/path="knowledge"/);
      expect(appSource).toMatch(/path="tensions"/);
      expect(appSource).toMatch(/path="advanced"/);
      expect(appSource).toMatch(/path="build"/);
      expect(askScreenSource).toMatch(/AskDiagnosticsSlot/);
    });
  });

  describe("Knowledge S002 ownership intact", () => {
    it("Library/Update/Site remain the sole Knowledge owners with their S002 implementations", () => {
      expect(libraryScreenSource).toMatch(/SourcesTable/);
      expect(updateScreenSource).toMatch(/IndexingConfigCard/);
      expect(siteScreenSource).toMatch(/KnowledgeProfileGenerateWizard/);
      expect(siteScreenSource).not.toMatch(/KnowledgeProfileLegacyBanner/);
      expect(siteScreenSource).not.toMatch(/getKnowledgeProfilePresets/);
      expect(libraryScreenSource).not.toMatch(/components\/sources/);
      expect(updateScreenSource).not.toMatch(/components\/indexing/);
      expect(siteScreenSource).not.toMatch(/components\/knowledge-profile/);
    });

    it("App.tsx still registers canonical Knowledge routes under /knowledge", () => {
      expect(appSource).toMatch(/path="library"/);
      expect(appSource).toMatch(/path="update"/);
      expect(appSource).toMatch(/path="site"/);
    });
  });
});
