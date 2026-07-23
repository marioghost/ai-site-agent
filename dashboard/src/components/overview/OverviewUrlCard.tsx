import { ExternalLink, Globe, Network } from "lucide-react";
import { MetricCard } from "../../ui";

interface Props {
  label: string;
  url: string | null | undefined;
  emptyLabel: string;
  kind: "site" | "sitemap";
  tone?: "blue" | "teal";
}

export default function OverviewUrlCard({
  label,
  url,
  emptyLabel,
  kind,
  tone = kind === "site" ? "blue" : "teal",
}: Props) {
  const Icon = kind === "site" ? Globe : Network;
  const hasUrl = Boolean(url?.trim());
  const metricTone = tone === "teal" ? "info" : "info";

  return (
    <MetricCard
      label={label}
      icon={<Icon size={18} />}
      tone={metricTone}
      value={
        hasUrl ? (
          <a
            href={url!}
            target="_blank"
            rel="noopener noreferrer"
            title={url!}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 500 }}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 280 }}>
              {url}
            </span>
            <ExternalLink size={14} />
          </a>
        ) : (
          emptyLabel
        )
      }
      hover
    />
  );
}
