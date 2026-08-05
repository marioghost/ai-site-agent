import { RefreshCw } from "lucide-react";
import { IconButton, PageHeader, Tag } from "../../../../ui";

interface Props {
  title: string;
  subtitle: string;
  updatedAt: Date | null;
  updatedLabel: string;
  refreshLabel: string;
  timeframeLabel?: string;
  onRefresh: () => void;
  refreshing?: boolean;
}

export default function AnalyticsHeader({
  title,
  subtitle,
  updatedAt,
  updatedLabel,
  refreshLabel,
  timeframeLabel,
  onRefresh,
  refreshing = false,
}: Props) {
  const formatted =
    updatedAt != null
      ? updatedAt.toLocaleString(undefined, {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      : "—";

  return (
    <PageHeader
      title={title}
      subtitle={subtitle}
      actions={
        <>
          {timeframeLabel && <Tag>{timeframeLabel}</Tag>}
          <span className="ds-caption">
            {updatedLabel}: {formatted}
          </span>
          <IconButton
            label={refreshLabel}
            title={refreshLabel}
            onClick={onRefresh}
            disabled={refreshing}
          >
            <RefreshCw size={16} className={refreshing ? "ds-animate-spin" : undefined} />
          </IconButton>
        </>
      }
    />
  );
}
