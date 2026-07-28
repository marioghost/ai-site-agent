import { useState } from "react";
import { useTranslation } from "../../i18n";
import type { BuildInfo } from "../../types";
import { Button, SectionCard, StatusBadge, Tag } from "../../ui";

type Props = {
  build?: BuildInfo | null;
};

function PathNode({
  label,
  tone,
}: {
  label: string;
  tone: "active" | "flag" | "diagnostic" | "planned";
}) {
  const variant =
    tone === "active"
      ? "ready"
      : tone === "flag"
        ? "info"
        : tone === "diagnostic"
          ? "neutral"
          : "pending";
  return <StatusBadge variant={variant} label={label} size="sm" />;
}

export default function ArchitectureStatusVisual({ build }: Props) {
  const { t } = useTranslation();
  const [detailsOpen, setDetailsOpen] = useState(false);

  const caps = build?.deployed_capabilities ?? {};
  const flagOn = (name: string) => caps[name]?.value === true;

  const executiveOn = flagOn("KNOWLEDGE_OS_EXECUTIVE_ENABLED");
  const reasoningOn = flagOn("REASONING_SERVICE_ENABLED");
  const eaOn = flagOn("EVIDENCE_ASSEMBLY_ENABLED");

  const activeNodes: string[] = [
    t("architecture.node.user"),
    t("architecture.node.chat"),
  ];
  if (executiveOn) activeNodes.push(t("architecture.node.executive"));
  if (reasoningOn) activeNodes.push(t("architecture.node.reasoning"));
  activeNodes.push(t("architecture.node.rag"), t("architecture.node.rps"));
  if (eaOn) activeNodes.push(t("architecture.node.ea"));
  activeNodes.push(
    t("architecture.node.dfp"),
    t("architecture.node.ollama"),
    t("architecture.node.answer")
  );

  return (
    <SectionCard title={t("architecture.title")} subtitle={t("architecture.subtitle")}>
      <div className="ds-stack" style={{ gap: "1rem" }}>
        <div>
          <p className="ds-text-secondary" style={{ marginTop: 0 }}>
            {t("architecture.active_path_label")}
          </p>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            {activeNodes.map((label, i) => (
              <span
                key={`${label}-${i}`}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
              >
                {i > 0 ? <span aria-hidden>→</span> : null}
                <PathNode label={label} tone="active" />
              </span>
            ))}
          </div>
          <p className="ds-text-secondary" style={{ fontSize: "0.85rem" }}>
            {t("architecture.active_path_note")}
          </p>
        </div>

        <div>
          <p className="ds-text-secondary" style={{ marginTop: 0 }}>
            {t("architecture.seams_label")}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
            <Tag>
              {t("architecture.node.executive")}:{" "}
              {executiveOn
                ? t("architecture.tone.active")
                : t("architecture.tone.flag_gated")}
            </Tag>
            <Tag>
              {t("architecture.node.reasoning")}:{" "}
              {reasoningOn
                ? t("architecture.tone.active")
                : t("architecture.tone.flag_gated")}
            </Tag>
            <Tag>
              {t("architecture.node.ea")}:{" "}
              {eaOn ? t("architecture.tone.active") : t("architecture.tone.flag_gated")}
            </Tag>
          </div>
        </div>

        <div>
          <p className="ds-text-secondary" style={{ marginTop: 0 }}>
            {t("architecture.diagnostic_path_label")}
          </p>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            {(
              [
                t("architecture.node.si"),
                t("architecture.node.memory"),
                t("architecture.node.tension"),
                t("architecture.node.health"),
              ] as const
            ).map((label, i) => (
              <span
                key={label}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
              >
                {i > 0 ? <span aria-hidden>→</span> : null}
                <PathNode label={label} tone="diagnostic" />
              </span>
            ))}
          </div>
          <p className="ds-text-secondary" style={{ fontSize: "0.85rem" }}>
            {t("architecture.memory_isolated")}
          </p>
        </div>

        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDetailsOpen((v) => !v)}
            aria-expanded={detailsOpen}
          >
            {detailsOpen
              ? t("architecture.hide_details")
              : t("architecture.show_details")}
          </Button>
          {detailsOpen ? (
            <p className="ds-text-secondary" style={{ marginBottom: 0 }}>
              {t("architecture.details_body")}
            </p>
          ) : null}
        </div>
      </div>
    </SectionCard>
  );
}
