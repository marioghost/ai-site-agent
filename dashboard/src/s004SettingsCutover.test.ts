import { describe, expect, it } from "vitest";
import { PRODUCT_NAV } from "./lib/navConfig";
import { canAccessRoute } from "./lib/permissions";
import appSource from "./App.tsx?raw";
import usersPageSource from "./pages/UsersPage.tsx?raw";
import settingsLayoutSource from "./layouts/SettingsLayout.tsx?raw";
import generalScreenSource from "./features/settings/general/GeneralScreen.tsx?raw";
import modelsScreenSource from "./features/settings/models/ModelsScreen.tsx?raw";
import answersScreenSource from "./features/settings/answers/AnswersScreen.tsx?raw";
import accessScreenSource from "./features/settings/access/AccessScreen.tsx?raw";

describe("S004 Settings product cutover", () => {
  it("keeps canonical Settings owners in product nav", () => {
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
    expect(settings.items.some((item) => item.to === "/users")).toBe(false);
  });

  it("registers canonical Settings routes", () => {
    expect(appSource).toMatch(/path="general"/);
    expect(appSource).toMatch(/path="models"/);
    expect(appSource).toMatch(/path="answers"/);
    expect(appSource).toMatch(/path="access"/);
  });

  it("keeps legacy Users route only as a redirect", () => {
    expect(usersPageSource).toMatch(/Navigate/);
    expect(usersPageSource).not.toMatch(/listUsers|DataTable|createUser/);
    expect(usersPageSource).toMatch(/\/settings\/access/);
  });

  it("removes S001 placeholders from canonical Settings screens", () => {
    expect(modelsScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(answersScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(accessScreenSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("adds SettingsLayout section navigation for canonical owners", () => {
    expect(settingsLayoutSource).toMatch(/\/settings\/general/);
    expect(settingsLayoutSource).toMatch(/\/settings\/models/);
    expect(settingsLayoutSource).toMatch(/\/settings\/answers/);
    expect(settingsLayoutSource).toMatch(/\/settings\/access/);
  });

  it("migrates owner implementation into Settings feature modules without legacy component imports", () => {
    expect(modelsScreenSource).toMatch(/OllamaModelsPanel/);
    expect(answersScreenSource).toMatch(/applyAgentPreset|deriveAgentPreset/);
    expect(accessScreenSource).toMatch(/listUsers/);

    expect(generalScreenSource).not.toMatch(/components\/settings/);
    expect(modelsScreenSource).not.toMatch(/components\/settings/);
    expect(answersScreenSource).not.toMatch(/components\/settings/);
    expect(accessScreenSource).not.toMatch(/components\/settings/);
    expect(accessScreenSource).not.toMatch(/pages\/UsersPage/);
  });

  it("keeps Models/Answers free of advanced retrieval engine knobs", () => {
    expect(modelsScreenSource).not.toMatch(/SettingsAdvancedSection|RetrievalEnginePanel/);
    expect(answersScreenSource).not.toMatch(/SettingsAdvancedSection|RetrievalEnginePanel/);
    expect(modelsScreenSource).not.toMatch(/MigrationFlagsPanel/);
    expect(answersScreenSource).not.toMatch(/MigrationFlagsPanel/);
    expect(accessScreenSource).not.toMatch(/MigrationFlagsPanel/);
  });

  it("enforces Access route permissions and Users redirect target", () => {
    expect(canAccessRoute("admin", "/settings/access")).toBe(true);
    expect(canAccessRoute("operator", "/settings/access")).toBe(false);
    expect(canAccessRoute("viewer", "/settings/access")).toBe(false);
    expect(canAccessRoute("admin", "/users")).toBe(true);
  });

  it("does not regress Knowledge/Insights product nav owners from S002/S003", () => {
    const knowledge = PRODUCT_NAV.find(
      (entry) => entry.kind === "section" && entry.labelKey === "nav.knowledge"
    );
    expect(knowledge).toBeTruthy();
    if (!knowledge || knowledge.kind !== "section") {
      throw new Error("knowledge nav section missing");
    }
    expect(knowledge.items.map((item) => item.to)).toEqual([
      "/knowledge/library",
      "/knowledge/update",
      "/knowledge/site",
    ]);

    const insights = PRODUCT_NAV.find(
      (entry) => entry.kind === "section" && entry.labelKey === "nav.insights"
    );
    expect(insights).toBeTruthy();
    if (!insights || insights.kind !== "section") {
      throw new Error("insights nav section missing");
    }
    expect(insights.items.map((item) => item.to)).toEqual([
      "/insights/performance",
      "/insights/activity",
    ]);
  });
});
