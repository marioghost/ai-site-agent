import { RefreshCw } from "lucide-react";
import { IconButton, PageHeader } from "../../ui";

interface Props {
  title: string;
  subtitle: string;
  updatedAt: Date | null;
  updatedLabel: string;
  refreshLabel: string;
  onRefresh: () => void;
  refreshing?: boolean;
  status?: React.ReactNode;
}

export default function OverviewHeader({
  title,
  subtitle,
  updatedAt,
  updatedLabel,
  refreshLabel,
  onRefresh,
  refreshing = false,
  status,
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
      status={status}
      actions={
        <>
          <span className="ds-page-header__meta">
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
