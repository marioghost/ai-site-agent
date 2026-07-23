import { describe, expect, it } from "vitest";
import { en } from "../../i18n/en";
import { uk } from "../../i18n/uk";
import { KNOWLEDGE_PROFILE_LEGACY_BANNER_KEYS } from "./knowledgeProfileLegacyBannerKeys";

describe("KnowledgeProfileLegacyBanner i18n", () => {
  for (const key of KNOWLEDGE_PROFILE_LEGACY_BANNER_KEYS) {
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

  it("banner copy mentions legacy migration and future Knowledge OS direction", () => {
    const combined = KNOWLEDGE_PROFILE_LEGACY_BANNER_KEYS.map((key) => en[key]).join(" ");
    expect(combined.toLowerCase()).toContain("legacy");
    expect(combined.toLowerCase()).toContain("epistemic");
    expect(combined.toLowerCase()).toContain("claims");
    expect(combined.toLowerCase()).toContain("reasoning");
  });
});
