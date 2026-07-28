import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { uk } from "../i18n/uk";

const KEYS = [
  "migration_flags.flag.legacy_doc_type_canonical_enabled",
  "migration_flags.flag.legacy_doc_type_canonical_enabled.help",
] as const;

describe("Step 055 legacy doc-type canonical flag i18n", () => {
  for (const key of KEYS) {
    it(`en defines ${key}`, () => {
      expect(en[key]).toBeTruthy();
      expect(en[key]).not.toBe(key);
    });
    it(`uk defines ${key}`, () => {
      expect(uk[key]).toBeTruthy();
      expect(uk[key]).not.toBe(key);
    });
  }

  it("EN copy describes legacy selection without claiming Memory authority", () => {
    const label = en[KEYS[0]];
    const help = en[KEYS[1]];
    expect(label.toLowerCase()).toContain("legacy");
    expect(help.toLowerCase()).toContain("memory authority");
    expect(help.toLowerCase()).toContain("off");
  });
});
