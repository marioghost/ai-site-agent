type TranslateFn = (key: string) => string;

/** Human-readable label for a query intent slug (i18n with fallback). */
export function intentLabel(intent: string, t: TranslateFn): string {
  const normalized = intent.trim().toLowerCase() || "unknown";
  const key = `intent.${normalized}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return normalized.replace(/_/g, " ");
}
