import type { Settings } from "../../types";
import {
  RETRIEVAL_PROFILES,
  type RetrievalProfileName,
} from "../../lib/retrievalEngineDefaults";
import {
  Alert,
  Field,
  FormGrid,
  HelpText,
  Input,
  SectionCard,
  Select,
} from "../../ui";

type Props = {
  settings: Settings;
  onChange: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

const PROFILE_OPTIONS: RetrievalProfileName[] = [
  "automatic",
  "fast",
  "balanced",
  "high_precision",
];

function numOrEmpty(v: number | null | undefined): string {
  return v == null || Number.isNaN(v) ? "" : String(v);
}

function parseOptionalInt(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  return Number.isNaN(n) ? null : n;
}

function parseOptionalFloat(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  return Number.isNaN(n) ? null : n;
}

export default function RetrievalEnginePanel({ settings, onChange, t }: Props) {
  const profile = (settings.retrieval_profile ?? "automatic") as RetrievalProfileName;
  const profileLimits = RETRIEVAL_PROFILES[profile] ?? RETRIEVAL_PROFILES.automatic;

  return (
    <SectionCard
      title={t("settings.retrieval_engine.title")}
      subtitle={t("settings.retrieval_engine.subtitle_simple")}
    >
      <Alert variant="info">{t("settings.retrieval_engine.automatic_note")}</Alert>

      <FormGrid columns={1}>
        <Field label={t("settings.retrieval_engine.profile")}>
          <Select
            value={profile}
            onChange={(e) => onChange("retrieval_profile", e.target.value)}
          >
            {PROFILE_OPTIONS.map((name) => (
              <option key={name} value={name}>
                {t(`settings.retrieval_engine.profile.${name}`)}
              </option>
            ))}
          </Select>
          <HelpText>{t(`settings.retrieval_engine.profile_hint.${profile}`)}</HelpText>
        </Field>
      </FormGrid>

      <FormGrid columns={3}>
        <Field label={t("settings.retrieval_engine.top_k_dense")}>
          <Input
            type="number"
            placeholder={String(profileLimits.top_k_dense)}
            value={numOrEmpty(settings.top_k_dense)}
            onChange={(e) => onChange("top_k_dense", parseOptionalInt(e.target.value))}
          />
        </Field>
        <Field label={t("settings.retrieval_engine.top_k_lexical")}>
          <Input
            type="number"
            placeholder={String(profileLimits.top_k_lexical)}
            value={numOrEmpty(settings.top_k_lexical)}
            onChange={(e) => onChange("top_k_lexical", parseOptionalInt(e.target.value))}
          />
        </Field>
        <Field label={t("settings.retrieval_engine.document_limit")}>
          <Input
            type="number"
            placeholder={String(profileLimits.document_limit)}
            value={numOrEmpty(settings.document_limit)}
            onChange={(e) => onChange("document_limit", parseOptionalInt(e.target.value))}
          />
        </Field>
        <Field label={t("settings.retrieval_engine.minimum_score")}>
          <Input
            type="number"
            step="0.01"
            placeholder={String(profileLimits.minimum_score)}
            value={numOrEmpty(settings.minimum_retrieval_score)}
            onChange={(e) =>
              onChange("minimum_retrieval_score", parseOptionalFloat(e.target.value))
            }
          />
        </Field>
      </FormGrid>
      <HelpText>{t("settings.retrieval_engine.override_hint")}</HelpText>
    </SectionCard>
  );
}
