import type { SourceSemanticProfile } from "../../../types";
import { useTranslation } from "../../../i18n";
import { SectionCard } from "../../../ui";

type Props = {
  profile: SourceSemanticProfile | Record<string, unknown> | null | undefined;
  summary?: string;
  profileVersion?: string;
};

function asList(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (value == null || value === "") return "—";
  return String(value);
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="ds-intel-kv__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function SourceIntelligencePanel({ profile, summary, profileVersion }: Props) {
  const { t } = useTranslation();
  const p = (profile || {}) as SourceSemanticProfile;

  if (!profile || Object.keys(profile).length === 0) {
    return (
      <SectionCard title={t("sources.intelligence.title")}>
        <p className="ds-caption">{t("sources.intelligence.empty")}</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title={t("sources.intelligence.title")}
      subtitle={profileVersion ? `${profileVersion} · ${p.generator || "rules"}` : undefined}
    >
      {summary && <p className="ds-intelligence-summary">{summary}</p>}
      <dl className="ds-intel-kv">
        <Row label={t("sources.intelligence.main_topic")} value={p.main_topic || "—"} />
        <Row label={t("sources.intelligence.subtopics")} value={asList(p.subtopics)} />
        <Row label={t("sources.intelligence.purpose")} value={p.document_purpose || "—"} />
        <Row label={t("sources.intelligence.entity_type")} value={p.entity_type || "—"} />
        <Row label={t("sources.intelligence.intents")} value={asList(p.supported_intents)} />
        <Row label={t("sources.intelligence.tags")} value={asList(p.semantic_tags)} />
        <Row label={t("sources.intelligence.keywords")} value={asList(p.search_keywords)} />
        <Row label={t("sources.intelligence.synonyms")} value={asList(p.synonyms)} />
        <Row label={t("sources.intelligence.suitable_for")} value={asList(p.suitable_for)} />
        <Row label={t("sources.intelligence.not_suitable_for")} value={asList(p.not_suitable_for)} />
        <Row
          label={t("sources.intelligence.confidence")}
          value={typeof p.confidence === "number" ? `${(p.confidence * 100).toFixed(0)}%` : "—"}
        />
      </dl>
    </SectionCard>
  );
}
