import type { TranslationDict, UiLanguage } from "./types";
import { en } from "./en";
import { uk } from "./uk";

const LOCALES: Record<UiLanguage, TranslationDict> = { uk, en };

export function getLocale(lang: UiLanguage): TranslationDict {
  return LOCALES[lang];
}

export function translate(
  lang: UiLanguage,
  key: string,
  vars?: Record<string, string | number>,
  fallback?: string
): string {
  const dict = LOCALES[lang];
  let text = dict[key] ?? fallback ?? key;
  if (vars) {
    text = text.replace(/\{(\w+)\}/g, (_, k: string) =>
      vars[k] !== undefined ? String(vars[k]) : `{${k}}`
    );
  }
  return text;
}

/** Status / trace keys use dynamic suffixes — lookup with fallback. */
export function translateDynamic(
  lang: UiLanguage,
  prefix: string,
  value: string
): string {
  const key = `${prefix}.${value}`;
  const dict = LOCALES[lang];
  if (dict[key]) return dict[key];
  return value.replace(/_/g, " ");
}
