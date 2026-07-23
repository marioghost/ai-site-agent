import { useTranslation } from "../../i18n";
import type { AppliedKnowledgeConfig } from "../../types";
import { DiagnosticSection, KvGrid, asList } from "./DiagnosticSection";

export default function ChatAppliedConfig({
  config,
}: {
  config: AppliedKnowledgeConfig | null | undefined;
}) {
  const { t } = useTranslation();
  if (!config) return null;

  const list = (items: string[]) => asList(items);

  return (
    <DiagnosticSection title={t("knowledge_profile.debug.title")} defaultOpen={false}>
      <KvGrid
        items={[
          { label: t("knowledge_profile.debug.intent"), value: config.detected_intent || "—" },
          {
            label: t("knowledge_profile.debug.topic"),
            value: config.matched_topic_label || config.matched_topic_key || "—",
          },
          { label: t("knowledge_profile.debug.aliases"), value: list(config.matched_aliases) },
          { label: t("knowledge_profile.debug.expansions"), value: list(config.query_expansions) },
          { label: t("knowledge_profile.debug.boost_docs"), value: list(config.boosted_document_types) },
          {
            label: t("knowledge_profile.debug.deprioritize_docs"),
            value: list(config.deprioritized_document_types),
          },
          { label: t("knowledge_profile.debug.boost_hints"), value: list(config.boosted_content_hints) },
          {
            label: t("knowledge_profile.debug.deprioritize_hints"),
            value: list(config.deprioritized_content_hints),
          },
          { label: t("knowledge_profile.debug.supplemental"), value: list(config.supplemental_queries) },
        ]}
      />
    </DiagnosticSection>
  );
}
