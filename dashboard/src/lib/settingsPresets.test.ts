import { describe, expect, it } from "vitest";
import { applyAgentPreset, deriveAgentPreset } from "./settingsPresets";
import type { Settings } from "../types";

const baseSettings = {
  retrieval_profile: "automatic",
  llm_mode_profile: "balanced",
} as Settings;

describe("settingsPresets semantic retrieval UI", () => {
  it("defaults to automatic preset", () => {
    expect(deriveAgentPreset(baseSettings)).toBe("automatic");
  });

  it("clears legacy weight JSON when applying presets", () => {
    const dirty = {
      ...baseSettings,
      document_priorities_json: '{"product_page":0.3}',
      scoring_weights_json: '{"semantic":0.5}',
      intent_profiles_json: "{}",
    } as Settings;
    const next = applyAgentPreset(dirty, "automatic");
    expect(next.document_priorities_json).toBe("");
    expect(next.scoring_weights_json).toBe("");
    expect(next.intent_profiles_json).toBe("");
  });

  it("does not inject deprecated Settings boost fields", () => {
    const next = applyAgentPreset(baseSettings, "balanced");
    expect("homepage_boost_enabled" in next).toBe(false);
    expect("title_match_boost" in next).toBe(false);
    expect("heading_match_boost" in next).toBe(false);
    expect("homepage_boost_value" in next).toBe(false);
    expect("short_query_lexical_boost" in next).toBe(false);
  });

  it("does not expose content priority helpers", async () => {
    const mod = await import("./settingsPresets");
    expect("applyContentPriority" in mod).toBe(false);
    expect("deriveContentPriority" in mod).toBe(false);
  });
});
