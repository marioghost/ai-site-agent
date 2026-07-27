import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { uk } from "../i18n/uk";
import { UNDERSTANDING_PAGE_I18N_KEYS } from "../pages/understandingPageKeys";
import {
  UNDERSTANDING_WRITE_ACTION_TOKENS,
  countTensions,
  fetchAllTensions,
  filterTensions,
  formatIdList,
  paginateTensions,
  resolveUnderstandingViewState,
  tensionDiagnosticJson,
  tensionRowKey,
  type TensionLike,
} from "./understandingTensions";

const sampleDeficit: TensionLike = {
  tension_type: "support_deficit",
  claim_ids: [11],
  observation_ref_ids: [],
  evidence_link_ids: [],
  summary: "Possible support deficit: active claim has no supporting evidence",
};

const sampleConflict: TensionLike = {
  tension_type: "conflict",
  claim_ids: [1, 2],
  observation_ref_ids: [9],
  evidence_link_ids: [4, 5],
  summary: "Possible conflict: observation 9 supports claim 1 and conflicts with claim 2",
};

describe("Understanding tensions helpers", () => {
  it("formats empty id lists as dash", () => {
    expect(formatIdList([])).toBe("—");
    expect(formatIdList(null)).toBe("—");
  });

  it("formats id lists deterministically", () => {
    expect(formatIdList([3, 1, 2])).toBe("3, 1, 2");
  });

  it("builds stable row keys from provenance", () => {
    expect(tensionRowKey(sampleConflict)).toBe("conflict|1-2|9|4-5");
  });

  it("counts empty response as zeros", () => {
    expect(countTensions([])).toEqual({
      total: 0,
      support_deficit: 0,
      conflict: 0,
    });
  });

  it("counts support deficit and conflict separately", () => {
    expect(countTensions([sampleDeficit, sampleConflict, sampleDeficit])).toEqual({
      total: 3,
      support_deficit: 2,
      conflict: 1,
    });
  });

  it("filters by possible support deficit", () => {
    const filtered = filterTensions([sampleDeficit, sampleConflict], "support_deficit");
    expect(filtered).toEqual([sampleDeficit]);
  });

  it("filters by possible conflict", () => {
    const filtered = filterTensions([sampleDeficit, sampleConflict], "conflict");
    expect(filtered).toEqual([sampleConflict]);
  });

  it("filter all returns every item", () => {
    const items = [sampleDeficit, sampleConflict];
    expect(filterTensions(items, "all")).toEqual(items);
  });

  it("paginates deterministically and clamps page", () => {
    const items = Array.from({ length: 5 }, (_, i) => ({
      ...sampleDeficit,
      claim_ids: [i + 1],
    }));
    const page1 = paginateTensions(items, 1, 2);
    expect(page1.items.map((x) => x.claim_ids[0])).toEqual([1, 2]);
    expect(page1.totalPages).toBe(3);
    const page3 = paginateTensions(items, 3, 2);
    expect(page3.items.map((x) => x.claim_ids[0])).toEqual([5]);
    const overflow = paginateTensions(items, 99, 2);
    expect(overflow.page).toBe(3);
  });

  it("changing filter conceptually resets to page 1 via caller contract", () => {
    // Documented page contract: callers must set page=1 when filter changes.
    const filtered = filterTensions([sampleDeficit, sampleConflict], "conflict");
    const paged = paginateTensions(filtered, 1, 25);
    expect(paged.page).toBe(1);
    expect(paged.items).toEqual([sampleConflict]);
  });

  it("builds API-shaped diagnostic JSON for expanded provenance", () => {
    const json = tensionDiagnosticJson(sampleConflict);
    const parsed = JSON.parse(json) as TensionLike;
    expect(parsed).toEqual(sampleConflict);
    expect(json).toContain("Possible conflict");
    expect(json).not.toContain("EpistemicClaim");
    expect(json).not.toContain("session");
  });

  it("fetchAllTensions aggregates API pages", async () => {
    const pages = [
      { items: [sampleDeficit], total: 2, page: 1, page_size: 1 },
      { items: [sampleConflict], total: 2, page: 2, page_size: 1 },
    ];
    let calls = 0;
    const all = await fetchAllTensions(async ({ page }) => {
      calls += 1;
      return pages[page - 1];
    }, 1);
    expect(calls).toBe(2);
    expect(all).toEqual([sampleDeficit, sampleConflict]);
  });

  it("fetchAllTensions handles empty response", async () => {
    const all = await fetchAllTensions(async () => ({
      items: [],
      total: 0,
      page: 1,
      page_size: 200,
    }));
    expect(all).toEqual([]);
  });

  it("resolves loading, error, empty, and ready view states", () => {
    expect(
      resolveUnderstandingViewState({ loading: true, error: null, itemCount: 0 })
    ).toBe("loading");
    expect(
      resolveUnderstandingViewState({
        loading: false,
        error: "Failed",
        itemCount: 0,
      })
    ).toBe("error");
    expect(
      resolveUnderstandingViewState({ loading: false, error: null, itemCount: 0 })
    ).toBe("empty");
    expect(
      resolveUnderstandingViewState({ loading: false, error: null, itemCount: 2 })
    ).toBe("ready");
    expect(
      resolveUnderstandingViewState({
        loading: false,
        error: "Failed",
        itemCount: 2,
      })
    ).toBe("ready");
  });
});

describe("Understanding page i18n uncertainty wording", () => {
  for (const key of UNDERSTANDING_PAGE_I18N_KEYS) {
    it(`en defines ${key}`, () => {
      const value = en[key];
      expect(value).toBeTruthy();
      expect(value).not.toBe(key);
    });

    it(`uk defines ${key}`, () => {
      const value = uk[key];
      expect(value).toBeTruthy();
      expect(value).not.toBe(key);
    });
  }

  it("English type labels communicate uncertainty", () => {
    expect(en["understanding.type.support_deficit"]).toBe("Possible support deficit");
    expect(en["understanding.type.conflict"]).toBe("Possible conflict");
    expect(en["understanding.empty"]).toBe("No possible memory issues were surfaced");
  });

  it("Ukrainian type labels communicate uncertainty", () => {
    expect(uk["understanding.type.support_deficit"]).toBe("Можливий дефіцит підтверджень");
    expect(uk["understanding.type.conflict"]).toBe("Можливий конфлікт");
    expect(uk["understanding.empty"]).toBe("Можливих проблем пам'яті не виявлено");
  });

  it("banner states tensions are hypotheses not facts", () => {
    const banner = en["understanding.banner"].toLowerCase();
    expect(banner).toContain("hypothesis");
    expect(banner).toMatch(/not (a )?fact|not knowledge|not (a )?belief/);
    expect(banner).not.toContain("confirmed conflict");
    expect(banner).not.toContain("knowledge error");
  });

  it("avoids confirmed/knowledge-error wording in EN labels", () => {
    const blob = UNDERSTANDING_PAGE_I18N_KEYS.map((k) => en[k]).join(" ").toLowerCase();
    expect(blob).not.toContain("knowledge error");
    expect(blob).not.toContain("confirmed conflict");
    expect(blob).toContain("not a verified fact");
    expect(blob).toContain("possible support deficit");
    expect(blob).toContain("possible conflict");
  });
});

describe("Understanding page is presentation-only", () => {
  it("documents banned write/action tokens for this surface", () => {
    expect(UNDERSTANDING_WRITE_ACTION_TOKENS).toEqual(
      expect.arrayContaining(["resolve", "investigate", "classify", "persist"])
    );
  });

  it("page module is a default export presentation surface", async () => {
    const mod = await import("../pages/UnderstandingPage");
    expect(typeof mod.default).toBe("function");
  });
});

describe("existing dashboard routes remain registered", () => {
  it("permissions gate understanding as admin-only alongside users", async () => {
    const { canAccessRoute } = await import("./permissions");
    expect(canAccessRoute("admin", "/understanding")).toBe(true);
    expect(canAccessRoute("operator", "/understanding")).toBe(false);
    expect(canAccessRoute("viewer", "/understanding")).toBe(false);
    expect(canAccessRoute("admin", "/users")).toBe(true);
    expect(canAccessRoute("admin", "/overview")).toBe(true);
  });
});
