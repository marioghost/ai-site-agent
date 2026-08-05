import { useEffect, useState } from "react";
import { clearRetrievalCache, getSettings, updateSettings } from "../../../api/client";
import { useTranslation } from "../../../i18n";
import type { Settings } from "../../../types";
import {
  type AgentPreset,
  applyAgentPreset,
  applySmartSearch,
  deriveAgentPreset,
  isSmartSearchEnabled,
  retrievalSettingsChanged,
} from "../../../lib/settingsPresets";
import {
  Alert,
  Button,
  CheckboxField,
  Field,
  FormStack,
  HelpText,
  Input,
  LoadingState,
  PageHeader,
  PageLayout,
  SectionCard,
  Select,
} from "../../../ui";

const PRESETS: AgentPreset[] = ["automatic", "fast", "balanced", "high_precision"];

export default function AnswersScreen() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then((s) => {
      setSettings(s);
      setSavedSnapshot(s);
    });
  }, []);

  if (!settings) return <LoadingState label={t("common.loading_settings")} />;

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings({ ...settings, [key]: value });

  const agentPreset = deriveAgentPreset(settings);

  async function onSave() {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    const before = savedSnapshot;
    try {
      const saved = await updateSettings(settings);
      const cacheRefreshed = !!before && retrievalSettingsChanged(before, settings);
      if (cacheRefreshed) {
        try {
          await clearRetrievalCache();
        } catch {
          /* non-fatal */
        }
      }
      setSettings(saved);
      setSavedSnapshot(saved);
      setMessage(cacheRefreshed ? t("settings.saved_with_cache_refresh") : t("settings.saved"));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("settings.error_save"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageLayout>
      <PageHeader
        title={t("nav.answers")}
        subtitle={t("settings.simple.answers_page_subtitle")}
        actions={
          <Button variant="primary" onClick={() => void onSave()} disabled={saving}>
            {saving ? t("common.saving") : t("common.save")}
          </Button>
        }
      />

      {message && (
        <Alert
          variant={
            message === t("settings.saved") || message === t("settings.saved_with_cache_refresh")
              ? "success"
              : "error"
          }
        >
          {message}
        </Alert>
      )}

      <SectionCard
        title={t("settings.simple.search_title")}
        subtitle={t("settings.simple.search_subtitle")}
      >
        <div className="ds-settings-presets">
          {PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              className={`ds-settings-presets__card${
                agentPreset === preset ? " ds-settings-presets__card--active" : ""
              }`}
              onClick={() => setSettings(applyAgentPreset(settings, preset))}
            >
              <span className="ds-settings-presets__label">
                {t(`settings.simple.preset.${preset}`)}
              </span>
              <span className="ds-settings-presets__hint">
                {t(`settings.simple.preset_hint.${preset}`)}
              </span>
            </button>
          ))}
        </div>

        <FormStack>
          <CheckboxField
            label={t("settings.simple.smart_search")}
            checked={isSmartSearchEnabled(settings)}
            onChange={(e) => setSettings(applySmartSearch(settings, e.target.checked))}
          />
        </FormStack>
        <HelpText>{t("settings.simple.search_footer")}</HelpText>
      </SectionCard>

      <SectionCard
        title={t("settings.simple.agent_title")}
        subtitle={t("settings.simple.agent_subtitle")}
      >
        <FormStack>
          <Field label={t("settings.generation.fallback")}>
            <Input
              value={settings.fallback_answer}
              onChange={(e) => update("fallback_answer", e.target.value)}
            />
            <HelpText>{t("settings.simple.fallback_hint")}</HelpText>
          </Field>
          <Field label={t("settings.answer.response_language")}>
            <Select
              value={settings.default_response_language ?? "uk"}
              onChange={(e) => update("default_response_language", e.target.value)}
            >
              <option value="uk">{t("lang.uk")}</option>
              <option value="en">{t("lang.en")}</option>
            </Select>
          </Field>
          <CheckboxField
            label={t("settings.toggles.enable_sources")}
            checked={settings.enable_sources && settings.enable_source_links}
            onChange={(e) => {
              const on = e.target.checked;
              setSettings({ ...settings, enable_sources: on, enable_source_links: on });
            }}
          />
          <CheckboxField
            label={t("settings.toggles.enable_chat_logs")}
            checked={settings.enable_chat_logs}
            onChange={(e) => update("enable_chat_logs", e.target.checked)}
          />
        </FormStack>
      </SectionCard>
    </PageLayout>
  );
}
