import { useTranslation } from "../../i18n";
import type { RequestMetadata } from "../../types";
import { DiagnosticSection, KvGrid } from "./DiagnosticSection";

export default function ChatQueryInfo({ meta }: { meta: RequestMetadata }) {
  const { t } = useTranslation();

  return (
    <DiagnosticSection title={t("trace.request_info")} defaultOpen={false}>
      <KvGrid
        items={[
          { label: "request_id", value: meta.request_id, mono: true },
          { label: "session_id", value: meta.session_id || t("common.dash"), mono: true },
          { label: "IP", value: meta.user_ip || t("common.dash") },
          { label: "User agent", value: meta.user_agent || t("common.dash") },
          { label: "Referrer", value: meta.referrer || t("common.dash") },
          { label: t("trace.meta.knowledge_version"), value: meta.knowledge_version },
          { label: t("trace.meta.retrieval_mode"), value: meta.retrieval_mode },
          { label: t("trace.meta.query_intent"), value: t(`intent.${meta.query_intent}`) },
          {
            label: t("trace.meta.time"),
            value: meta.created_at ? new Date(meta.created_at).toLocaleString() : t("common.dash"),
          },
        ]}
      />
    </DiagnosticSection>
  );
}
