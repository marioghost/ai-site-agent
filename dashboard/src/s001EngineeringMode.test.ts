/**
 * S001 — Engineering Mode storage, nav, permissions contracts.
 */
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import {
  ENGINEERING_MODE_STORAGE_KEY,
  readEngineeringModeEnabled,
  resetEngineeringModeOff,
  writeEngineeringModeEnabled,
} from "./lib/engineeringModeStorage";
import { buildNavEntries, PRODUCT_NAV, ENGINEERING_NAV } from "./lib/navConfig";
import { canAccessRoute, isEngineeringPath } from "./lib/permissions";
import appSource from "./App.tsx?raw";
import migrationPanelSource from "./components/settings/MigrationFlagsPanel.tsx?raw";
import settingsPageSource from "./pages/SettingsPage.tsx?raw";
import generalSource from "./features/settings/general/GeneralScreen.tsx?raw";
import { en } from "./i18n/en";
import { uk } from "./i18n/uk";

describe("S001 Engineering Mode storage", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: {
        getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
        setItem: (k: string, v: string) => {
          mem.set(k, String(v));
        },
        removeItem: (k: string) => {
          mem.delete(k);
        },
        clear: () => mem.clear(),
      },
    });
  });

  afterEach(() => {
    mem.clear();
  });

  it("uses frozen key engineering.mode.enabled", () => {
    expect(ENGINEERING_MODE_STORAGE_KEY).toBe("engineering.mode.enabled");
  });

  it("defaults off", () => {
    expect(readEngineeringModeEnabled()).toBe(false);
  });

  it("persists true/false", () => {
    writeEngineeringModeEnabled(true);
    expect(localStorage.getItem(ENGINEERING_MODE_STORAGE_KEY)).toBe("true");
    expect(readEngineeringModeEnabled()).toBe(true);
    writeEngineeringModeEnabled(false);
    expect(localStorage.getItem(ENGINEERING_MODE_STORAGE_KEY)).toBe("false");
    expect(readEngineeringModeEnabled()).toBe(false);
  });

  it("resetEngineeringModeOff clears to off", () => {
    writeEngineeringModeEnabled(true);
    resetEngineeringModeOff();
    expect(readEngineeringModeEnabled()).toBe(false);
  });
});

describe("S001 navConfig", () => {
  it("product nav has no engineering section when mode off", () => {
    const entries = buildNavEntries(false);
    expect(entries).toEqual(PRODUCT_NAV);
    expect(entries.some((e) => e.kind === "section" && e.labelKey === "nav.engineering")).toBe(
      false
    );
  });

  it("appends engineering nav when mode on", () => {
    const entries = buildNavEntries(true);
    expect(entries[entries.length - 1]).toEqual(ENGINEERING_NAV);
  });

  it("product top-level labels are glossary keys", () => {
    expect(PRODUCT_NAV.some((e) => e.kind === "item" && e.to === "/home")).toBe(true);
    expect(PRODUCT_NAV.some((e) => e.kind === "item" && e.to === "/ask")).toBe(true);
  });
});

describe("S001 permissions", () => {
  it("maps RFC-101 product routes", () => {
    expect(canAccessRoute("viewer", "/home")).toBe(true);
    expect(canAccessRoute("viewer", "/ask")).toBe(false);
    expect(canAccessRoute("operator", "/ask")).toBe(true);
    expect(canAccessRoute("operator", "/settings/general")).toBe(false);
    expect(canAccessRoute("admin", "/settings/general")).toBe(true);
    expect(canAccessRoute("admin", "/engineering/status")).toBe(true);
    expect(canAccessRoute("operator", "/engineering/status")).toBe(false);
  });

  it("detects engineering paths", () => {
    expect(isEngineeringPath("/engineering")).toBe(true);
    expect(isEngineeringPath("/engineering/status")).toBe(true);
    expect(isEngineeringPath("/home")).toBe(false);
  });
});

describe("S001 glossary i18n", () => {
  it("defines scaffold and nav keys in en/uk", () => {
    expect(en["scaffold.not_migrated"]).toBe("This section has not been migrated yet.");
    expect(uk["scaffold.not_migrated"]).toBeTruthy();
    expect(en["nav.home"]).toBe("Home");
    expect(uk["nav.home"]).toBeTruthy();
    expect(en["nav.ask"]).toBe("Chat");
  });
});

describe("S001 App routes contracts", () => {
  it("registers engineering routes and settings general", () => {
    expect(appSource).toMatch(/\/engineering/);
    expect(appSource).toMatch(/settings\/general|path="general"/);
    expect(appSource).toMatch(/RequireEngineeringMode/);
    // S007 (G6-P3) retired `/overview` as the redirect target for `/` and
    // `*` (both now go to `/home`); `/overview` itself remains registered
    // as a redirect-compatibility route — see s007HomeDefaultOverview.test.ts.
    expect(appSource).toMatch(/path="\/overview"/);
  });

  it("General hosts engineering mode toggle", () => {
    expect(generalSource).toMatch(/useEngineeringMode/);
    expect(generalSource).toMatch(/engineering_mode/);
  });

  it("legacy SettingsPage still does not mount MigrationFlagsPanel", () => {
    expect(settingsPageSource).not.toMatch(/MigrationFlagsPanel/);
    expect(migrationPanelSource).toMatch(/export default function MigrationFlagsPanel/);
  });
});
