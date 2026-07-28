import { describe, expect, it } from "vitest";
import { en } from "../i18n/en";
import { uk } from "../i18n/uk";
import {
  isLegacyKpPresetsDisabledError,
  LEGACY_KP_PRESETS_DISABLED_CODE,
} from "./legacyKpPresetsDisabled";

const BANNER_KEY = "knowledge_profile.presets.disabled_banner";

describe("legacy KP presets disabled (Step 054)", () => {
  it("detects 410 with canonical detail code", () => {
    expect(
      isLegacyKpPresetsDisabledError({
        response: {
          status: 410,
          data: {
            detail: {
              code: LEGACY_KP_PRESETS_DISABLED_CODE,
              message: "Legacy Knowledge Profile presets are disabled.",
            },
          },
        },
      })
    ).toBe(true);
  });

  it("detects generic 410", () => {
    expect(isLegacyKpPresetsDisabledError({ response: { status: 410 } })).toBe(true);
  });

  it("ignores non-410 errors", () => {
    expect(isLegacyKpPresetsDisabledError({ response: { status: 500 } })).toBe(false);
    expect(isLegacyKpPresetsDisabledError(new Error("network"))).toBe(false);
  });

  it("EN/UK banner keys exist with approved meaning", () => {
    expect(en[BANNER_KEY]).toContain("Legacy Knowledge Profile presets are disabled");
    expect(en[BANNER_KEY]).toContain("Existing profiles remain active");
    expect(en[BANNER_KEY].toLowerCase()).toContain("import");
    expect(uk[BANNER_KEY]).toContain("Застарілі шаблони профілів знань вимкнено");
    expect(uk[BANNER_KEY]).toContain("Наявні профілі залишаються активними");
  });
});
