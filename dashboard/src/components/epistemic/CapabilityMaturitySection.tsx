import { useTranslation } from "../../i18n";
import { SectionCard, StatusBadge, type StatusVariant } from "../../ui";

type MaturityStatus =
  | "active"
  | "available_behind_flag"
  | "experimental"
  | "diagnostic_only"
  | "not_active"
  | "planned";

type MaturityItem = {
  id: string;
  status: MaturityStatus;
};

const IMPLEMENTED: MaturityItem[] = [
  { id: "indexed_sources", status: "active" },
  { id: "source_intelligence", status: "active" },
  { id: "observation_refs", status: "active" },
  { id: "claims", status: "active" },
  { id: "evidence_links", status: "active" },
  { id: "tension_surfacing", status: "diagnostic_only" },
  { id: "epistemic_api", status: "diagnostic_only" },
  { id: "epistemic_health_ui", status: "experimental" },
  { id: "operational_metrics", status: "diagnostic_only" },
];

const FLAG_GATED: MaturityItem[] = [
  { id: "executive_seam", status: "available_behind_flag" },
  { id: "reasoning_seam", status: "available_behind_flag" },
  { id: "evidence_assembly", status: "available_behind_flag" },
  { id: "advisory_sufficiency", status: "available_behind_flag" },
  { id: "advisory_speech_acts", status: "available_behind_flag" },
  { id: "speech_act_language", status: "available_behind_flag" },
];

const NOT_ACTIVE: MaturityItem[] = [
  { id: "memory_in_chat", status: "not_active" },
  { id: "memory_assisted_evidence", status: "not_active" },
  { id: "belief_revision", status: "planned" },
  { id: "semantic_conflict", status: "planned" },
  { id: "investigation", status: "planned" },
  { id: "active_maintenance", status: "planned" },
  { id: "gap_resolution", status: "planned" },
];

function statusVariant(status: MaturityStatus): StatusVariant {
  switch (status) {
    case "active":
      return "ready";
    case "available_behind_flag":
      return "info";
    case "experimental":
      return "processing";
    case "diagnostic_only":
      return "neutral";
    case "not_active":
      return "skipped";
    case "planned":
      return "pending";
  }
}

function MaturityList({ items }: { items: MaturityItem[] }) {
  const { t } = useTranslation();
  return (
    <ul className="ds-stack-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map((item) => (
        <li
          key={item.id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "0.75rem",
            padding: "0.35rem 0",
          }}
        >
          <span>{t(`maturity.item.${item.id}`)}</span>
          <StatusBadge
            variant={statusVariant(item.status)}
            label={t(`maturity.status.${item.status}`)}
          />
        </li>
      ))}
    </ul>
  );
}

export default function CapabilityMaturitySection() {
  const { t } = useTranslation();

  return (
    <SectionCard title={t("maturity.title")} subtitle={t("maturity.subtitle")}>
      <div className="ds-stack" style={{ gap: "1.25rem" }}>
        <div>
          <h3 className="ds-section-card__subtitle" style={{ marginBottom: "0.5rem" }}>
            {t("maturity.group.implemented")}
          </h3>
          <MaturityList items={IMPLEMENTED} />
        </div>
        <div>
          <h3 className="ds-section-card__subtitle" style={{ marginBottom: "0.5rem" }}>
            {t("maturity.group.flag_gated")}
          </h3>
          <MaturityList items={FLAG_GATED} />
        </div>
        <div>
          <h3 className="ds-section-card__subtitle" style={{ marginBottom: "0.5rem" }}>
            {t("maturity.group.not_active")}
          </h3>
          <MaturityList items={NOT_ACTIVE} />
        </div>
      </div>
    </SectionCard>
  );
}
