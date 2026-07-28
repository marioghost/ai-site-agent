/** Detect Step 054 HTTP 410 from Knowledge Profile preset endpoints. */
export const LEGACY_KP_PRESETS_DISABLED_CODE = "legacy_kp_presets_disabled";

export function isLegacyKpPresetsDisabledError(error: unknown): boolean {
  const err = error as {
    response?: {
      status?: number;
      data?: { detail?: { code?: string } | string };
    };
  };
  if (err?.response?.status !== 410) return false;
  const detail = err.response.data?.detail;
  if (detail && typeof detail === "object" && detail.code === LEGACY_KP_PRESETS_DISABLED_CODE) {
    return true;
  }
  // Treat any 410 from preset calls as the disabled gate (stale UI / older detail shapes).
  return true;
}
