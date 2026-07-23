import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getSettings } from "../api/client";
import { translate, translateDynamic } from "./translate";
import {
  DEFAULT_LANGUAGE,
  STORAGE_KEY,
  type UiLanguage,
} from "./types";

interface I18nContextValue {
  lang: UiLanguage;
  setLang: (lang: UiLanguage) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  jobStatusLabel: (status: string) => string;
  sourceStatusLabel: (status: string) => string;
  healthStatusLabel: (status: string) => string;
  cacheTypeLabel: (cacheType: string) => string;
  traceStepLabel: (name: string) => string;
  traceStatusLabel: (status: string) => string;
  indexingStageLabel: (stage: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readStoredLang(): UiLanguage | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "uk" || v === "en") return v;
  } catch {
    /* ignore */
  }
  return null;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<UiLanguage>(() => {
    return readStoredLang() ?? DEFAULT_LANGUAGE;
  });

  useEffect(() => {
    getSettings()
      .then((s) => {
        const stored = readStoredLang();
        if (stored) return;
        if (s.dashboard_language === "en" || s.dashboard_language === "uk") {
          setLangState(s.dashboard_language);
        }
      })
      .catch(() => {
        /* backend optional on first paint */
      });
  }, []);

  const setLang = useCallback((next: UiLanguage) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) =>
      translate(lang, key, vars),
    [lang]
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      lang,
      setLang,
      t,
      jobStatusLabel: (s) => translateDynamic(lang, "status.job", s),
      sourceStatusLabel: (s) => translateDynamic(lang, "status.source", s),
      healthStatusLabel: (s) => translateDynamic(lang, "status.health", s),
      cacheTypeLabel: (s) => translateDynamic(lang, "status.cache", s),
      traceStepLabel: (name) => translateDynamic(lang, "trace", name),
      traceStatusLabel: (s) => translateDynamic(lang, "status.trace", s),
      indexingStageLabel: (stage) => translateDynamic(lang, "indexing.stage", stage),
    }),
    [lang, setLang, t]
  );

  return (
    <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
  );
}

export function useTranslation(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within I18nProvider");
  }
  return ctx;
}
