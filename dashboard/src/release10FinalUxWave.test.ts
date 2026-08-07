import { readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import askScreenSource from "./features/ask/AskScreen.tsx?raw";
import activityScreenSource from "./features/insights/activity/ActivityScreen.tsx?raw";
import performanceScreenSource from "./features/insights/performance/PerformanceScreen.tsx?raw";
import accessScreenSource from "./features/settings/access/AccessScreen.tsx?raw";
import answersScreenSource from "./features/settings/answers/AnswersScreen.tsx?raw";
import generalScreenSource from "./features/settings/general/GeneralScreen.tsx?raw";
import homeScreenSource from "./features/home/HomeScreen.tsx?raw";
import askDiagnosticsSlotSource from "./features/ask/widgets/AskDiagnosticsSlot.tsx?raw";
import dashboardLayoutSource from "./components/layout/DashboardLayout.tsx?raw";
import viewportGateSource from "./components/layout/ViewportGate.tsx?raw";
import chatToolbarSource from "./components/chat/ChatToolbar.tsx?raw";
import chatAssistantSource from "./components/chat/ChatAssistantCard.tsx?raw";
import chatMessageListSource from "./components/chat/ChatMessageList.tsx?raw";
import pageLayoutSource from "./ui/components/PageLayout.tsx?raw";
import { en } from "./i18n/en";
import { uk } from "./i18n/uk";
import { filterActivityPage } from "./lib/activityFilter";
import { DASHBOARD_MIN_WIDTH_PX } from "./components/layout/ViewportGate";
import { PRODUCT_NAV, ENGINEERING_NAV } from "./lib/navConfig";
import { healthChecklistCopyKey } from "./lib/homeReadiness";
import { evaluatePerformancePresence } from "./lib/performanceAnalytics";
import { EMPTY_SOURCES, ZERO_RETRIEVAL } from "./lib/performanceAnalytics.fixtures";
import type { ChatLog } from "./types";

const productUxCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "ui/styles/product-ux.css"),
  "utf8"
);

function log(partial: Partial<ChatLog> & Pick<ChatLog, "id" | "user_message" | "assistant_answer">): ChatLog {
  return {
    session_id: "s",
    request_id: "r",
    used_context: false,
    cache_hit: false,
    cache_type: "none",
    retrieval_ms: 0,
    generation_ms: 0,
    polish_ms: 0,
    sources: [],
    created_at: "2026-08-05T00:00:00Z",
    ...partial,
  };
}

describe("Release 1.0 final UX wave — Home contracts", () => {
  it("uses the shared homeReadiness helper (single source of truth)", () => {
    expect(homeScreenSource).toMatch(/deriveHomeModel/);
    expect(homeScreenSource).toMatch(/healthChecklistCopyKey/);
    expect(homeScreenSource).not.toMatch(/readyToUse < totalSources/);
  });

  it("dedupes More links against primary/secondary CTAs", () => {
    expect(homeScreenSource).toMatch(/link\.to !== primary\.to && link\.to !== secondary\?\.to/);
  });

  it("verdict badge uses tone label, not duplicated state title", () => {
    expect(homeScreenSource).toMatch(/label=\{badgeLabel\(verdictTone\)\}/);
  });

  it("unknown health copy is distinct from degraded", () => {
    expect(healthChecklistCopyKey(null)).toBe("home.checklist.health_unknown");
    expect(en["home.checklist.health_unknown"]).toBeTruthy();
    expect(uk["home.checklist.health_unknown"]).toBeTruthy();
    expect(en["home.checklist.health_unknown"]).not.toMatch(/degraded|attention/i);
  });
});

describe("Release 1.0 final UX wave — Ask product density", () => {
  it("Ask uses product density when Eng Mode is off; Eng Mode enables turn selection", () => {
    expect(askScreenSource).toMatch(/density=\{engineeringModeOn \? "engineering" : "product"\}/);
    expect(askScreenSource).toMatch(/onSelectAssistant=\{engineeringModeOn \? selectAssistantTurn : undefined\}/);
    expect(askScreenSource).toMatch(/AskDiagnosticsSlot/);
  });

  it("assistant cards hide engineering metrics in product density", () => {
    expect(chatAssistantSource).toMatch(/!product/);
    expect(chatAssistantSource).toMatch(/!product && metadata/);
    expect(chatMessageListSource).toMatch(/density = \"engineering\"/);
  });

  it("toolbar does not render session UUID", () => {
    expect(chatToolbarSource).not.toMatch(/sessionId\.slice/);
    expect(chatToolbarSource).not.toMatch(/sessionId:/);
  });

  it("Ask Eng Mode slot mounts diagnostics beside chat", () => {
    expect(askDiagnosticsSlotSource).toMatch(/ChatDiagnosticsSidebar/);
  });
});

describe("Release 1.0 final UX wave — Activity page-local search", () => {
  const rows = [
    log({ id: 1, user_message: "Alpha question", assistant_answer: "Alpha answer" }),
    log({ id: 2, user_message: "Beta question", assistant_answer: "Other" }),
  ];

  it("filters only the provided page rows", () => {
    expect(filterActivityPage(rows, "alpha")).toHaveLength(1);
    expect(filterActivityPage(rows, "missing")).toHaveLength(0);
    expect(filterActivityPage(rows, "")).toHaveLength(2);
  });

  it("exposes honest page-scope wording in EN and UK", () => {
    expect(en["activity.filter.search_page"]).toMatch(/this page/i);
    expect(uk["activity.filter.search_page"]).toMatch(/сторінц/i);
    expect(en["activity.filter.search_help"]).toMatch(/this page/i);
    expect(en["activity.no_match"]).toMatch(/this page/i);
    expect(activityScreenSource).toMatch(/activity\.no_match/);
    expect(activityScreenSource).toMatch(/activity\.empty/);
    expect(activityScreenSource).toMatch(/total === 0/);
  });

  it("distinguishes load errors from empty activity", () => {
    expect(activityScreenSource).toMatch(/ErrorState/);
    expect(activityScreenSource).toMatch(/activity\.error_title/);
    expect(activityScreenSource).toMatch(/setErrorKey/);
    expect(en["activity.error_title"]).toBeTruthy();
    expect(uk["activity.error_title"]).toBeTruthy();
  });

  it("uses human card structure with expandable details", () => {
    expect(activityScreenSource).toMatch(/ds-activity-card/);
    expect(activityScreenSource).toMatch(/<details/);
    expect(activityScreenSource).not.toMatch(/logs\.title/);
  });
});

describe("Release 1.0 final UX wave — Insights / Settings / Shell", () => {
  it("Performance gates empty composition on meaningful data, not truthy objects", () => {
    expect(performanceScreenSource).toMatch(/nav\.performance/);
    expect(performanceScreenSource).toMatch(/evaluatePerformancePresence/);
    expect(performanceScreenSource).toMatch(/LoadingState/);
    expect(
      evaluatePerformancePresence({
        timeseries: [],
        popularCount: 0,
        problematicCount: 0,
        retrieval: ZERO_RETRIEVAL,
        sources: EMPTY_SOURCES,
        intents: [],
        topics: [],
        insights: null,
      }).isEmpty
    ).toBe(true);
  });

  it("Access and Answers titles/subtitles are product-facing", () => {
    expect(accessScreenSource).toMatch(/nav\.access/);
    expect(answersScreenSource).toMatch(/settings\.simple\.answers_page_subtitle/);
  });

  it("General keeps Engineering Mode toggle", () => {
    expect(generalScreenSource).toMatch(/useEngineeringMode/);
    expect(generalScreenSource).toMatch(/setEnabled/);
  });

  it("shell has skip link, main landmark, and viewport gate threshold", () => {
    expect(dashboardLayoutSource).toMatch(/ds-skip-link/);
    expect(dashboardLayoutSource).toMatch(/#main-content/);
    expect(dashboardLayoutSource).toMatch(/ViewportGate/);
    expect(pageLayoutSource).toMatch(/<main/);
    expect(viewportGateSource).toMatch(/DASHBOARD_MIN_WIDTH_PX = 1024/);
    expect(DASHBOARD_MIN_WIDTH_PX).toBe(1024);
    expect(viewportGateSource).not.toMatch(/role=\"dialog\"/);
    expect(productUxCss).toMatch(/max-width:\s*1023px/);
    expect(productUxCss).toMatch(/:focus-visible/);
    expect(productUxCss).toMatch(/ds-skip-link/);
  });

  it("EN/UK parity for wave keys", () => {
    const keys = [
      "home.checklist.knowledge_summary_skipped",
      "home.checklist.knowledge_waiting",
      "home.checklist.health_unknown",
      "home.metrics.sources_hint_skipped",
      "activity.filter.search_page",
      "activity.filter.search_help",
      "activity.no_match",
      "activity.error_title",
      "activity.error_description",
      "shell.viewport.hint",
      "common.search",
      "settings.simple.answers_page_subtitle",
    ];
    for (const key of keys) {
      expect(en[key], `missing EN ${key}`).toBeTruthy();
      expect(uk[key], `missing UK ${key}`).toBeTruthy();
    }
  });

  it("nav ownership remains product + engineering contracts", () => {
    expect(PRODUCT_NAV.some((e) => e.kind === "item" && e.labelKey === "nav.home")).toBe(true);
    expect(PRODUCT_NAV.some((e) => e.kind === "item" && e.labelKey === "nav.ask")).toBe(true);
    expect(ENGINEERING_NAV.items.length).toBe(5);
  });
});

describe("Release 1.0 final UX wave — reduced motion", () => {
  it("respects prefers-reduced-motion for skip-link transition", () => {
    expect(productUxCss).toMatch(/prefers-reduced-motion/);
  });
});
