/** Frozen Engineering Mode localStorage key (S001 Q7). Do not alias. */
export const ENGINEERING_MODE_STORAGE_KEY = "engineering.mode.enabled";

export function readEngineeringModeEnabled(): boolean {
  try {
    return localStorage.getItem(ENGINEERING_MODE_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function writeEngineeringModeEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(ENGINEERING_MODE_STORAGE_KEY, enabled ? "true" : "false");
  } catch {
    /* ignore */
  }
}

/** Q5 — reset Mode OFF (logout / cross-user isolation). */
export function resetEngineeringModeOff(): void {
  writeEngineeringModeEnabled(false);
}
