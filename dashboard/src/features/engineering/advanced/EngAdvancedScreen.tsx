import { useEffect, useState } from "react";
import {
  clearAllCaches,
  clearAnswerCache,
  clearRetrievalCache,
  getSettings,
  updateSettings,
} from "../../../api/client";
import { useTranslation } from "../../../i18n";
import type { Settings } from "../../../types";
import { Alert, Button, LoadingState, PageHeader, PageLayout } from "../../../ui";
import SettingsAdvancedSection from "./widgets/SettingsAdvancedSection";

/**
 * S006 (G7-P5) — Engineering owner for advanced retrieval/chunking/cache/
 * tracing knobs. Product Settings (General/Models/Answers/Access) never
 * mounts this section; it lives only here, gated behind Engineering Mode.
 */
export default function EngAdvancedScreen() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cacheBusy, setCacheBusy] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then(setSettings);
  }, []);

  if (!settings) return <LoadingState label={t("common.loading_settings")} />;

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings({ ...settings, [key]: value });

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = await updateSettings(settings);
      setSettings(saved);
      setMessage(t("settings.saved"));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("settings.error_save"));
    } finally {
      setSaving(false);
    }
  }

  async function handleClearCache(kind: "retrieval" | "answer" | "all") {
    setCacheBusy(kind);
    setMessage(null);
    try {
      if (kind === "all") await clearAllCaches();
      else if (kind === "answer") await clearAnswerCache();
      else await clearRetrievalCache();
      setMessage(t("settings.cache.clear_success"));
    } catch {
      setMessage(t("common.error"));
    } finally {
      setCacheBusy(null);
    }
  }

  return (
    <PageLayout className="ds-page--wide">
      <PageHeader
        title={t("nav.eng_advanced")}
        subtitle={t("eng.advanced.subtitle")}
        actions={
          <Button variant="primary" onClick={() => void handleSave()} disabled={saving}>
            {saving ? t("common.saving") : t("common.save")}
          </Button>
        }
      />

      {message && <Alert variant={message === t("settings.saved") ? "success" : "info"}>{message}</Alert>}

      <SettingsAdvancedSection
        settings={settings}
        onChange={update}
        t={t}
        onClearCache={(kind) => void handleClearCache(kind)}
        cacheBusy={cacheBusy}
      />
    </PageLayout>
  );
}
