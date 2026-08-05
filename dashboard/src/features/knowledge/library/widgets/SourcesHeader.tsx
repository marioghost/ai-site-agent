import { Download, Play, RefreshCw } from "lucide-react";
import { Button, PageHeader } from "../../../../ui";

type Props = {
  title: string;
  subtitle: string;
  refreshLabel: string;
  exportLabel: string;
  indexLabel: string;
  loading?: boolean;
  indexing?: boolean;
  onRefresh: () => void;
  onExport: () => void;
  onIndexAll: () => void;
};

export default function SourcesHeader({
  title,
  subtitle,
  refreshLabel,
  exportLabel,
  indexLabel,
  loading = false,
  indexing = false,
  onRefresh,
  onExport,
  onIndexAll,
}: Props) {
  return (
    <PageHeader
      title={title}
      subtitle={subtitle}
      actions={
        <>
          <Button variant="secondary" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? "ds-animate-spin" : undefined} />
            {refreshLabel}
          </Button>
          <Button variant="secondary" onClick={onExport}>
            <Download size={16} />
            {exportLabel}
          </Button>
          <Button variant="primary" onClick={onIndexAll} disabled={indexing}>
            <Play size={14} />
            {indexLabel}
          </Button>
        </>
      }
    />
  );
}
