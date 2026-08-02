import { useEffect, useState } from "react";
import {
  clearAllCaches,
  clearRetrievalCache,
  getModels,
  getSettings,
  updateSettings,
} from "../api/client";
import type { OllamaModel, Settings } from "../types";
import SettingsAdvancedSection from "../components/settings/SettingsAdvancedSection";
import SettingsHelpAccordion from "../components/settings/SettingsHelpAccordion";
import OllamaModelsPanel from "../components/settings/OllamaModelsPanel";
import { useTranslation } from "../i18n";
import type { UiLanguage } from "../i18n";
import {
  type AgentPreset,
  applyAgentPreset,
  applySmartSearch,
  deriveAgentPreset,
  isSmartSearchEnabled,
  retrievalSettingsChanged,
} from "../lib/settingsPresets";
import {
  Alert,
  Button,
  CheckboxField,
  Field,
  FormGrid,
  FormStack,
  HelpText,
  Input,
  LoadingState,
  PageHeader,
  PageLayout,
  SectionCard,
  Select,
} from "../ui";

const PRESETS: AgentPreset[] = ["automatic", "fast", "balanced", "high_precision"];

export default function SettingsPage() {
  const { t, setLang } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState<Settings | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [ollamaReachable, setOllamaReachable] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cacheBusy, setCacheBusy] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  useEffect(() => {
    getSettings().then((s) => {
      setSettings(s);
      setSavedSnapshot(s);
    });
    getModels()
      .then((r) => {
        setModels(r.models);
        setOllamaReachable(r.ollama_reachable !== false);
      })
      .catch(() => {
        setModels([]);
        setOllamaReachable(false);
      });
  }, []);

  if (!settings) return <LoadingState label={t("common.loading_settings")} />;

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) =>
    setSettings({ ...settings, [key]: value });

  const onDashboardLangChange = (lang: UiLanguage) => {
    update("dashboard_language", lang);
    setLang(lang);
  };

  async function handleClearCache(kind: "retrieval" | "answer" | "all") {
    setCacheBusy(kind);
    setMessage(null);
    try {
      if (kind === "all") await clearAllCaches();
      else await clearRetrievalCache();
      setMessage(t("settings.cache.clear_success"));
    } catch {
      setMessage(t("common.error"));
    } finally {
      setCacheBusy(null);
    }
  }

  const onSave = async () => {
    setSaving(true);
    setMessage(null);
    const before = savedSnapshot;
    try {
      const saved = await updateSettings(settings);
      if (before && retrievalSettingsChanged(before, settings)) {
        try {
          await clearRetrievalCache();
        } catch {
          /* non-fatal */
        }
      }
      setSettings(saved);
      setSavedSnapshot(saved);
      setMessage(
        before && retrievalSettingsChanged(before, settings)
          ? t("settings.saved_with_cache_refresh")
          : t("settings.saved")
      );
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setMessage(err?.response?.data?.detail || t("settings.error_save"));
    } finally {
      setSaving(false);
    }
  };

  const agentPreset = deriveAgentPreset(settings);
  const modelNames = models.map((m) => m.name);

  return (
    <PageLayout>
      <PageHeader
        title={t("settings.title")}
        subtitle={t("settings.subtitle_simple")}
        actions={
          <Button variant="primary" onClick={() => void onSave()} disabled={saving}>
            {saving ? t("common.saving") : t("settings.save")}
          </Button>
        }
      />

      {message && (
        <Alert
          variant={
            message === t("settings.saved") ||
            message === t("settings.saved_with_cache_refresh")
              ? "success"
              : "error"
          }
        >
          {message}
        </Alert>
      )}

      <SectionCard
        title={t("settings.simple.interface_title")}
        subtitle={t("settings.simple.interface_subtitle")}
      >
        <FormGrid columns={2}>
          <Field label={t("settings.dashboard_language.label")}>
            <Select
              value={settings.dashboard_language ?? "uk"}
              onChange={(e) => onDashboardLangChange(e.target.value as UiLanguage)}
            >
              <option value="uk">{t("lang.uk")}</option>
              <option value="en">{t("lang.en")}</option>
            </Select>
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
        </FormGrid>
      </SectionCard>

      <SectionCard
        title={t("settings.simple.models_title")}
        subtitle={t("settings.simple.models_subtitle")}
      >
        <FormGrid columns={2}>
          <Field label={t("settings.models.llm")}>
            {modelNames.length > 0 ? (
              <Select
                value={settings.llm_model}
                onChange={(e) => update("llm_model", e.target.value)}
              >
                {!modelNames.includes(settings.llm_model) && (
                  <option value={settings.llm_model}>{settings.llm_model}</option>
                )}
                {modelNames.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                value={settings.llm_model}
                onChange={(e) => update("llm_model", e.target.value)}
              />
            )}
          </Field>
          <Field label={t("settings.models.embedding")}>
            <Input
              value={settings.embedding_model}
              onChange={(e) => update("embedding_model", e.target.value)}
            />
          </Field>
        </FormGrid>
        <OllamaModelsPanel
          settings={settings}
          models={models}
          ollamaReachable={ollamaReachable}
          onModelsChange={setModels}
          onSelectLlmModel={(model) => update("llm_model", model)}
        />
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
          <CheckboxField
            label={t("settings.toggles.enable_sources")}
            checked={settings.enable_sources && settings.enable_source_links}
            onChange={(e) => {
              const on = e.target.checked;
              update("enable_sources", on);
              update("enable_source_links", on);
            }}
          />
          <CheckboxField
            label={t("settings.toggles.enable_chat_logs")}
            checked={settings.enable_chat_logs}
            onChange={(e) => update("enable_chat_logs", e.target.checked)}
          />
        </FormStack>
      </SectionCard>

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
          <CheckboxField
            label={t("settings.retrieval.debug")}
            checked={settings.enable_retrieval_debug}
            onChange={(e) => update("enable_retrieval_debug", e.target.checked)}
          />
        </FormStack>
        <HelpText>{t("settings.simple.search_footer")}</HelpText>
      </SectionCard>

      <SettingsAdvancedSection
        open={advancedOpen}
        onToggle={() => setAdvancedOpen((v) => !v)}
        settings={settings}
        onChange={update}
        t={t}
        onClearCache={handleClearCache}
        cacheBusy={cacheBusy}
      />

      <SettingsHelpAccordion t={t} />
    </PageLayout>
  );
}
