import { describe, expect, it } from "vitest";
import { PRODUCT_NAV } from "./lib/navConfig";
import appSource from "./App.tsx?raw";
import sourcesPageSource from "./pages/SourcesPage.tsx?raw";
import indexingPageSource from "./pages/IndexingPage.tsx?raw";
import knowledgeProfilePageSource from "./pages/KnowledgeProfilePage.tsx?raw";
import knowledgeLayoutSource from "./layouts/KnowledgeLayout.tsx?raw";
import libraryScreenSource from "./features/knowledge/library/LibraryScreen.tsx?raw";
import updateScreenSource from "./features/knowledge/update/UpdateScreen.tsx?raw";
import siteScreenSource from "./features/knowledge/site/SiteScreen.tsx?raw";

describe("S002 Knowledge product cutover", () => {
  it("keeps canonical Knowledge owners in product nav", () => {
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
    expect(knowledge.items.some((item) => item.to === "/sources")).toBe(false);
    expect(knowledge.items.some((item) => item.to === "/indexing")).toBe(false);
    expect(knowledge.items.some((item) => item.to === "/knowledge-profile")).toBe(false);
  });

  it("registers canonical Knowledge routes", () => {
    expect(appSource).toMatch(/path="library"/);
    expect(appSource).toMatch(/path="update"/);
    expect(appSource).toMatch(/path="site"/);
  });

  it("keeps legacy Knowledge routes only as redirects", () => {
    expect(sourcesPageSource).toMatch(/Navigate/);
    expect(sourcesPageSource).not.toMatch(/SourcesTable|SourcesHeader|listSources/);
    expect(sourcesPageSource).toMatch(/\/knowledge\/library/);
    expect(indexingPageSource).toMatch(/Navigate/);
    expect(indexingPageSource).not.toMatch(/IndexingConfigCard|reindexAll|getIndexStatus/);
    expect(indexingPageSource).toMatch(/\/knowledge\/update/);
    expect(knowledgeProfilePageSource).toMatch(/Navigate/);
    expect(knowledgeProfilePageSource).not.toMatch(/KnowledgeProfileGenerateWizard|updateKnowledgeProfile/);
    expect(knowledgeProfilePageSource).toMatch(/\/knowledge\/site/);
  });

  it("removes S001 placeholders from canonical Knowledge screens", () => {
    expect(libraryScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(updateScreenSource).not.toMatch(/MigrationPlaceholder/);
    expect(siteScreenSource).not.toMatch(/MigrationPlaceholder/);
  });

  it("adds KnowledgeLayout section navigation for canonical owners", () => {
    expect(knowledgeLayoutSource).toMatch(/\/knowledge\/library/);
    expect(knowledgeLayoutSource).toMatch(/\/knowledge\/update/);
    expect(knowledgeLayoutSource).toMatch(/\/knowledge\/site/);
  });

  it("migrates owner implementation into Knowledge feature modules", () => {
    expect(libraryScreenSource).toMatch(/SourcesTable/);
    expect(updateScreenSource).toMatch(/IndexingConfigCard/);
    expect(siteScreenSource).toMatch(/KnowledgeProfileLegacyBanner/);
    expect(libraryScreenSource).not.toMatch(/components\/sources/);
    expect(updateScreenSource).not.toMatch(/components\/indexing/);
    expect(siteScreenSource).not.toMatch(/components\/knowledge-profile/);
  });
});
