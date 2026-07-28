import { Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  exportKnowledgeProfile,
  getKnowledgeProfile,
  getKnowledgeProfilePresets,
  importKnowledgeProfile,
  loadKnowledgeProfilePreset,
  updateKnowledgeProfile,
} from "../api/client";
import KnowledgeProfileGenerateWizard from "../components/knowledge-profile/KnowledgeProfileGenerateWizard";
import KnowledgeProfileLegacyBanner from "../components/knowledge-profile/KnowledgeProfileLegacyBanner";
import { isLegacyKpPresetsDisabledError } from "../lib/legacyKpPresetsDisabled";
import type { KnowledgeProfile, KnowledgeProfilePreset } from "../types";
import { useTranslation } from "../i18n";
import {
  Alert,
  Button,
  CheckboxField,
  Field,
  FormGrid,
  Input,
  IconButton,
  LoadingState,
  PageHeader,
  PageLayout,
  SectionCard,
  Select,
  Textarea,
} from "../ui";

function lines(text: string): string[] {
  return text
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

export default function KnowledgeProfilePage() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<KnowledgeProfile | null>(null);
  const [presets, setPresets] = useState<KnowledgeProfilePreset[]>([]);
  const [presetsUnavailable, setPresetsUnavailable] = useState(false);
  const [advancedJson, setAdvancedJson] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showReindexWarn, setShowReindexWarn] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getKnowledgeProfile().then((p) => {
      setProfile(p);
      setAdvancedJson(JSON.stringify(p, null, 2));
    });
    getKnowledgeProfilePresets()
      .then((list) => {
        setPresets(list);
        setPresetsUnavailable(false);
      })
      .catch((err: unknown) => {
        setPresets([]);
        if (isLegacyKpPresetsDisabledError(err)) {
          setPresetsUnavailable(true);
        }
      });
  }, []);

  if (!profile) {
    return (
      <PageLayout>
        <LoadingState label={t("common.loading_settings")} />
      </PageLayout>
    );
  }

  const update = (next: KnowledgeProfile) => {
    setProfile(next);
    setAdvancedJson(JSON.stringify(next, null, 2));
    setShowReindexWarn(true);
  };

  const onSave = async () => {
    setBusy(true);
    setMessage(null);
    try {
      let payload = profile;
      if (showAdvanced) {
        payload = JSON.parse(advancedJson) as KnowledgeProfile;
      }
      const saved = await updateKnowledgeProfile(payload);
      setProfile(saved);
      setAdvancedJson(JSON.stringify(saved, null, 2));
      setMessage(t("knowledge_profile.saved"));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string | string[] } } };
      const detail = err?.response?.data?.detail;
      setMessage(
        Array.isArray(detail) ? detail.join("; ") : detail || t("knowledge_profile.error_save")
      );
    } finally {
      setBusy(false);
    }
  };

  const onLoadPreset = async (presetId: string) => {
    if (!confirm(t("knowledge_profile.preset_confirm"))) return;
    setBusy(true);
    try {
      const loaded = await loadKnowledgeProfilePreset(presetId);
      update(loaded);
      setPresetsUnavailable(false);
      setMessage(t("knowledge_profile.preset_loaded"));
    } catch (err: unknown) {
      if (isLegacyKpPresetsDisabledError(err)) {
        setPresetsUnavailable(true);
        setPresets([]);
        setMessage(t("knowledge_profile.presets.disabled_banner"));
      } else {
        setMessage(t("knowledge_profile.error_preset"));
      }
    } finally {
      setBusy(false);
    }
  };

  const onExport = async () => {
    const data = await exportKnowledgeProfile();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "knowledge-profile.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const onImportFile = async (file: File) => {
    const text = await file.text();
    const data = JSON.parse(text);
    const saved = await importKnowledgeProfile(data);
    update(saved);
    setMessage(t("knowledge_profile.imported"));
  };

  const disabledBanner = t("knowledge_profile.presets.disabled_banner");
  const messageVariant =
    message === t("knowledge_profile.saved") ||
    message === t("knowledge_profile.imported") ||
    message === t("knowledge_profile.preset_loaded") ||
    message === t("knowledge_profile.generate.applied")
      ? "success"
      : message === disabledBanner
        ? "info"
        : "error";

  return (
    <PageLayout>
      <PageHeader title={t("knowledge_profile.title")} subtitle={t("knowledge_profile.subtitle")} />

      <KnowledgeProfileLegacyBanner />

      {presetsUnavailable ? <Alert variant="info">{disabledBanner}</Alert> : null}

      {showReindexWarn ? (
        <Alert variant="warning">{t("knowledge_profile.reindex_warning")}</Alert>
      ) : null}

      {message ? <Alert variant={messageVariant}>{message}</Alert> : null}

      <SectionCard title={t("knowledge_profile.presets.title")}>
        {!presetsUnavailable ? (
          <FormGrid columns={2}>
            <Field label={t("knowledge_profile.presets.load")}>
              <Select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) onLoadPreset(e.target.value);
                  e.target.value = "";
                }}
                disabled={busy}
              >
                <option value="">{t("knowledge_profile.presets.load")}</option>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </Select>
            </Field>
          </FormGrid>
        ) : null}
        <div className="ds-action-toolbar" style={{ marginTop: "var(--ds-space-4)" }}>
          <div className="ds-action-toolbar__start">
            <Button type="button" variant="secondary" size="sm" onClick={onExport}>
              {t("knowledge_profile.export")}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
              {t("knowledge_profile.import")}
            </Button>
          </div>
          <div className="ds-action-toolbar__end">
            <Button type="button" onClick={() => setShowWizard(true)}>
              {t("knowledge_profile.generate.start")}
            </Button>
          </div>
        </div>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onImportFile(f).catch(() => setMessage(t("knowledge_profile.error_import")));
            }}
          />
      </SectionCard>

      <SectionCard title={t("knowledge_profile.identity.title")}>
        <FormGrid columns={3}>
          <Field label={t("knowledge_profile.identity.display_name")}>
            <Input
              value={profile.site_display_name}
              onChange={(e) => update({ ...profile, site_display_name: e.target.value })}
            />
          </Field>
          <Field label={t("knowledge_profile.identity.organization")}>
            <Input
              value={profile.organization_name}
              onChange={(e) => update({ ...profile, organization_name: e.target.value })}
            />
          </Field>
          <Field label={t("knowledge_profile.identity.entity_type")}>
            <Input
              value={profile.entity_type}
              onChange={(e) => update({ ...profile, entity_type: e.target.value })}
            />
          </Field>
        </FormGrid>
        <FormGrid columns={1}>
          <Field label={t("knowledge_profile.identity.subject")}>
            <Input
              value={profile.site_subject}
              onChange={(e) => update({ ...profile, site_subject: e.target.value })}
            />
          </Field>
          <Field label={t("knowledge_profile.identity.aliases")}>
            <Textarea
              rows={3}
              value={profile.organization_aliases.join("\n")}
              onChange={(e) =>
                update({ ...profile, organization_aliases: lines(e.target.value) })
              }
              placeholder={t("knowledge_profile.identity.aliases_hint")}
            />
          </Field>
        </FormGrid>
      </SectionCard>

      <SectionCard title={t("knowledge_profile.overview_patterns")}>
        <Textarea
          rows={5}
          value={profile.overview_query_patterns.join("\n")}
          onChange={(e) =>
            update({ ...profile, overview_query_patterns: lines(e.target.value) })
          }
        />
      </SectionCard>

      <SectionCard
        title={t("knowledge_profile.topics.title")}
        subtitle={t("knowledge_profile.topics.hint")}
      >
        <div className="ds-kp-topics">
          {profile.important_topics.map((topic, idx) => (
            <article key={`${topic.key}-${idx}`} className="ds-kp-topic">
              <div className="ds-kp-topic__header">
                <div className="ds-kp-topic__heading">
                  <span className="ds-kp-topic__index">{idx + 1}</span>
                  <span className="ds-kp-topic__name">{topic.label || topic.key}</span>
                </div>
                <IconButton
                  label={t("common.delete")}
                  className="ds-kp-topic__delete"
                  onClick={() =>
                    update({
                      ...profile,
                      important_topics: profile.important_topics.filter((_, i) => i !== idx),
                    })
                  }
                >
                  <Trash2 size={16} />
                </IconButton>
              </div>
              <FormGrid columns={3}>
                <Field label={t("knowledge_profile.topics.key")}>
                  <Input
                    value={topic.key}
                    onChange={(e) => {
                      const topics = [...profile.important_topics];
                      topics[idx] = { ...topic, key: e.target.value };
                      update({ ...profile, important_topics: topics });
                    }}
                  />
                </Field>
                <Field label={t("knowledge_profile.topics.label")}>
                  <Input
                    value={topic.label}
                    onChange={(e) => {
                      const topics = [...profile.important_topics];
                      topics[idx] = { ...topic, label: e.target.value };
                      update({ ...profile, important_topics: topics });
                    }}
                  />
                </Field>
                <Field label={t("knowledge_profile.topics.strategy")}>
                  <Select
                    value={topic.answer_strategy}
                    onChange={(e) => {
                      const topics = [...profile.important_topics];
                      topics[idx] = {
                        ...topic,
                        answer_strategy: e.target.value as typeof topic.answer_strategy,
                      };
                      update({ ...profile, important_topics: topics });
                    }}
                  >
                    {["overview", "fact", "list", "table", "contact", "pricing", "generic"].map(
                      (s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      )
                    )}
                  </Select>
                </Field>
              </FormGrid>
              <Field label={t("knowledge_profile.topics.aliases")}>
                <Textarea
                  rows={2}
                  value={topic.aliases.join("\n")}
                  onChange={(e) => {
                    const topics = [...profile.important_topics];
                    topics[idx] = { ...topic, aliases: lines(e.target.value) };
                    update({ ...profile, important_topics: topics });
                  }}
                />
              </Field>
            </article>
          ))}
        </div>
        <div className="ds-kp-topics__footer">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() =>
              update({
                ...profile,
                important_topics: [
                  ...profile.important_topics,
                  {
                    key: `topic_${profile.important_topics.length + 1}`,
                    label: "",
                    aliases: [],
                    preferred_document_types: [],
                    preferred_content_hints: [],
                    answer_strategy: "generic",
                  },
                ],
              })
            }
          >
            {t("knowledge_profile.topics.add")}
          </Button>
        </div>
      </SectionCard>

      <SectionCard title={t("knowledge_profile.advanced_json")}>
        <CheckboxField
          label={t("knowledge_profile.advanced_json")}
          checked={showAdvanced}
          onChange={(e) => setShowAdvanced(e.target.checked)}
        />
        {showAdvanced ? (
          <Textarea
            rows={20}
            value={advancedJson}
            onChange={(e) => setAdvancedJson(e.target.value)}
            style={{ fontFamily: "monospace", fontSize: 12, marginTop: "var(--ds-space-4)" }}
          />
        ) : null}
      </SectionCard>

      <div className="ds-kp-page-footer">
        <Button onClick={onSave} disabled={busy}>
          {t("common.save")}
        </Button>
      </div>

      {showWizard ? (
        <KnowledgeProfileGenerateWizard
          onApplied={(p) => {
            update(p);
            setMessage(t("knowledge_profile.generate.applied"));
            setShowWizard(false);
          }}
          onClose={() => setShowWizard(false)}
        />
      ) : null}
    </PageLayout>
  );
}
