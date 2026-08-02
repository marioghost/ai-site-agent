/**
 * RFC-100 Step 065 — Product Settings / Overview ownership cleanup.
 * Source contracts via Vite `?raw` (no Node builtins; tsc-safe).
 */
import { describe, expect, it } from "vitest";
import settingsPageSource from "./pages/SettingsPage.tsx?raw";
import overviewSource from "./components/overview/OverviewKnowledgeOsPanel.tsx?raw";
import migrationPanelSource from "./components/settings/MigrationFlagsPanel.tsx?raw";
import appSource from "./App.tsx?raw";
import typesSource from "./types/index.ts?raw";
import type { MaintenanceObservation } from "./types";

describe("Step 065 Dashboard ownership", () => {
  it("Product Settings does not mount MigrationFlagsPanel", () => {
    expect(settingsPageSource).not.toMatch(/MigrationFlagsPanel/);
    expect(settingsPageSource).toMatch(/SettingsAdvancedSection/);
    expect(settingsPageSource).toMatch(/SettingsHelpAccordion/);
    expect(settingsPageSource).not.toMatch(/KNOWLEDGE_OS_EXECUTIVE_ENABLED/);
    expect(settingsPageSource).not.toMatch(/MAINTENANCE_EXECUTION_ENABLED/);
  });

  it("MigrationFlagsPanel remains relocatable (unmounted component kept)", () => {
    expect(migrationPanelSource).toMatch(/export default function MigrationFlagsPanel/);
    expect(migrationPanelSource).toMatch(/KNOWLEDGE_OS_EXECUTIVE_ENABLED/);
    expect(migrationPanelSource).toMatch(/Step 065/);
  });

  it("Overview does not render raw KOS migration flag catalog", () => {
    expect(overviewSource).not.toMatch(/KNOWLEDGE_OS_EXECUTIVE_ENABLED/);
    expect(overviewSource).not.toMatch(/REASONING_SERVICE_ENABLED/);
    expect(overviewSource).not.toMatch(/EVIDENCE_ASSEMBLY_ENABLED/);
    expect(overviewSource).not.toMatch(/memory_shadow_write_enabled/);
    expect(overviewSource).not.toMatch(/flags_intro/);
    expect(overviewSource).toMatch(/release_accepted/);
    expect(overviewSource).toMatch(/release_in_progress/);
    expect(overviewSource).toMatch(/memory_version/);
  });

  it("no Engineering Mode routes invented; settings route unchanged", () => {
    expect(appSource).not.toMatch(/\/engineering/);
    expect(appSource).toMatch(/path=["']\/settings["']/);
  });

  it("BuildInfo types allow additive maintenance_observation", () => {
    expect(typesSource).toMatch(/maintenance_observation\?/);
    expect(typesSource).toMatch(/interface MaintenanceObservation/);
    expect(typesSource).toMatch(/investigations_per_cycle/);
    const sample: MaintenanceObservation = {
      execution_enabled: true,
      investigations_per_cycle: 0,
      surface: "env",
      runtime_owner: "maintenance_orchestration",
    };
    expect(sample.investigations_per_cycle).toBe(0);
  });
});
