import { Link } from "react-router-dom";
import { useTranslation } from "../../i18n";
import type { BuildInfo, EpistemicHealthSummary } from "../../types";
import { MetricCard, MetricGrid, SectionCard, StatusBadge, Tag } from "../../ui";

type Props = {
  build?: BuildInfo | null;
  summary?: EpistemicHealthSummary | null;
  isAdmin?: boolean;
};

export default function OverviewKnowledgeOsPanel({
  build,
  summary,
  isAdmin = false,
}: Props) {
  const { t } = useTranslation();
  const release = build?.release_status;

  return (
    <SectionCard title={t("overview.kos.title")} subtitle={t("overview.kos.subtitle")}>
      <p style={{ marginTop: 0 }}>{t("overview.kos.blurb")}</p>

      {release ? (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.5rem",
            marginBottom: "0.75rem",
            alignItems: "center",
          }}
        >
          <StatusBadge
            variant="ready"
            label={t("overview.kos.release_accepted", { version: release.accepted })}
          />
          {release.in_progress ? (
            <StatusBadge
              variant="processing"
              label={t("overview.kos.release_in_progress", {
                version: release.in_progress,
              })}
            />
          ) : null}
          <Tag>
            {t("overview.kos.memory_version")}: {build?.memory_version ?? t("common.dash")}
          </Tag>
          <Tag>
            {t("overview.kos.knowledge_version")}:{" "}
            {build?.knowledge_version ?? t("common.dash")}
          </Tag>
        </div>
      ) : null}

      {isAdmin && summary ? (
        <MetricGrid columns={3}>
          <MetricCard
            label={t("overview.kos.real_open_tensions")}
            value={summary.real_open_tensions}
            tone="warning"
            hover={false}
            helper={t("overview.kos.real_open_tensions_help")}
          />
          <MetricCard
            label={t("overview.kos.real_claims")}
            value={summary.real_claims}
            tone="info"
            hover={false}
          />
          <MetricCard
            label={t("overview.kos.si_claims")}
            value={summary.source_intelligence_claims}
            tone="primary"
            hover={false}
          />
        </MetricGrid>
      ) : null}

      {isAdmin ? (
        <p style={{ marginBottom: 0 }}>
          <Link to="/diagnostics/epistemic-health">{t("overview.kos.open_health")}</Link>
        </p>
      ) : null}
    </SectionCard>
  );
}
