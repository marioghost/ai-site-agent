/**
 * Technical migration-flag catalog. RFC-100 Step 065 kept this unmounted
 * from Product Settings for future Engineering Mode reuse; S006 (G7-P5)
 * mounts this copy on `/engineering/build`. Do not remount on product
 * surfaces (see `components/settings/MigrationFlagsPanel.tsx`).
 */
import { useEffect, useState } from "react";
import { getBuildInfo } from "../../../../api/client";
import { useTranslation } from "../../../../i18n";
import type { BuildInfo, DeployedCapability } from "../../../../types";
import { Alert, LoadingState, SectionCard, StatusBadge } from "../../../../ui";

const FLAG_ORDER = [
  "KNOWLEDGE_OS_EXECUTIVE_ENABLED",
  "REASONING_SERVICE_ENABLED",
  "EVIDENCE_ASSEMBLY_ENABLED",
  "REASONING_SPEECH_ACTS_ENABLED",
  "enable_semantic_diagnostics_v2",
  "cache_namespace_v2_enabled",
  "memory_shadow_write_enabled",
  "memory_evidence_assist_enabled",
  "memory_canonical_shadow_enabled",
  "allow_legacy_kp_presets",
  "legacy_doc_type_canonical_enabled",
] as const;

function valueLabel(
  cap: DeployedCapability,
  t: (k: string) => string
): string {
  if (!cap.supported) return t("migration_flags.not_deployed");
  if (cap.value === true) return t("migration_flags.value_on");
  if (cap.value === false) return t("migration_flags.value_off");
  return t("common.dash");
}

export default function MigrationFlagsPanel() {
  const { t } = useTranslation();
  const [build, setBuild] = useState<BuildInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBuildInfo()
      .then((info) => {
        if (!cancelled) {
          setBuild(info);
          setError(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBuild(null);
          setError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <SectionCard title={t("migration_flags.title")}>
        <LoadingState label={t("common.loading")} />
      </SectionCard>
    );
  }

  if (error || !build) {
    return (
      <SectionCard title={t("migration_flags.title")}>
        <Alert variant="error">{t("migration_flags.error_load")}</Alert>
      </SectionCard>
    );
  }

  const caps = build.deployed_capabilities ?? {};
  const rows = FLAG_ORDER.map((key) => {
    const cap = caps[key] ?? {
      supported: false,
      value: null,
      surface: "unknown",
      friendly_name: key,
      default: false,
      effect: "",
      rollout: "",
    };
    return { key, cap };
  });

  return (
    <SectionCard
      title={t("migration_flags.title")}
      subtitle={t("migration_flags.subtitle")}
    >
      {build.release_status?.note ? (
        <Alert variant="info">{build.release_status.note}</Alert>
      ) : null}

      <div style={{ overflowX: "auto" }}>
        <table className="ds-table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th>{t("migration_flags.col.flag")}</th>
              <th>{t("migration_flags.col.friendly")}</th>
              <th>{t("migration_flags.col.value")}</th>
              <th>{t("migration_flags.col.default")}</th>
              <th>{t("migration_flags.col.supported")}</th>
              <th>{t("migration_flags.col.effect")}</th>
              <th>{t("migration_flags.col.rollout")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, cap }) => (
              <tr key={key}>
                <td>
                  <code>{key}</code>
                </td>
                <td>
                  {(() => {
                    const labelKey = `migration_flags.flag.${key}`;
                    const localized = t(labelKey);
                    return localized !== labelKey ? localized : cap.friendly_name || key;
                  })()}
                </td>
                <td>
                  <StatusBadge
                    variant={
                      !cap.supported
                        ? "skipped"
                        : cap.value
                          ? "ready"
                          : "neutral"
                    }
                    label={valueLabel(cap, t)}
                  />
                </td>
                <td>
                  {cap.default
                    ? t("migration_flags.value_on")
                    : t("migration_flags.value_off")}
                </td>
                <td>
                  {cap.supported
                    ? t("migration_flags.supported_yes")
                    : t("migration_flags.supported_no")}
                </td>
                <td>{cap.effect || t("common.dash")}</td>
                <td>{cap.rollout || t("common.dash")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="ds-kv-grid" style={{ marginTop: "1rem" }}>
        <div className="ds-kv-grid__row">
          <dt>{t("migration_flags.meta.release")}</dt>
          <dd>{build.release}</dd>
        </div>
        <div className="ds-kv-grid__row">
          <dt>{t("migration_flags.meta.commit")}</dt>
          <dd className="ds-kv-grid__mono">
            {build.git_commit_short || build.git_commit || t("common.dash")}
          </dd>
        </div>
        <div className="ds-kv-grid__row">
          <dt>{t("migration_flags.meta.build_time")}</dt>
          <dd>{build.build_time || t("common.dash")}</dd>
        </div>
        <div className="ds-kv-grid__row">
          <dt>{t("migration_flags.meta.alembic")}</dt>
          <dd className="ds-kv-grid__mono">{build.alembic_head || t("common.dash")}</dd>
        </div>
      </dl>
    </SectionCard>
  );
}
