import { useEffect, useState } from "react";
import { getModels, getSettings, updateSettings } from "../../../api/client";
import type { OllamaModel, Settings } from "../../../types";
import { useTranslation } from "../../../i18n";
import OllamaModelsPanel from "./widgets/OllamaModelsPanel";
import {
  Alert,
  Button,
  Field,
  FormGrid,
  Input,
  LoadingState,
  PageHeader,
  PageLayout,
  SectionCard,
  Select,
} from "../../../ui";

export default function ModelsScreen() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [ollamaReachable, setOllamaReachable] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then(setSettings);
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

  const modelNames = models.map((m) => m.name);

  async function onSave() {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = await updateSettings({
        llm_model: settings.llm_model,
        embedding_model: settings.embedding_model,
      });
      setSettings(saved);
      setMessage(t("settings.saved"));
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
        title={t("nav.models")}
        subtitle={t("settings.simple.models_subtitle")}
        actions={
          <Button variant="primary" onClick={() => void onSave()} disabled={saving}>
            {saving ? t("common.saving") : t("common.save")}
          </Button>
        }
      />

      {message && (
        <Alert variant={message === t("settings.saved") ? "success" : "error"}>{message}</Alert>
      )}

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
    </PageLayout>
  );
}
