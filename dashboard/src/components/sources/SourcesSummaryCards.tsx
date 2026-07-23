import type { KnowledgeBaseStatus } from "../../types";
import { MetricGrid } from "../../ui";
import {
  AlertCircle,
  Ban,
  Check,
  Clock,
  Database,
  RefreshCw,
} from "lucide-react";
import { formatCount } from "./sourceUtils";
import SourceSummaryCard from "./SourceSummaryCard";

type Props = {
  data: KnowledgeBaseStatus | null;
  lang: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

export default function SourcesSummaryCards({ data, lang, t }: Props) {
  const fmt = (n: number) => formatCount(n, lang);

  return (
    <MetricGrid columns={6}>
      <SourceSummaryCard
        tone="purple"
        icon={<Database size={18} />}
        label={t("sources.kpi.total")}
        value={fmt(data?.total_sources ?? 0)}
        helper={t("sources.kpi.total_help")}
      />
      <SourceSummaryCard
        tone="green"
        icon={<Check size={18} />}
        label={t("sources.kpi.ready")}
        value={fmt(data?.ready_to_use ?? 0)}
        helper={t("sources.kpi.ready_help")}
      />
      <SourceSummaryCard
        tone="orange"
        icon={<Clock size={18} />}
        label={t("sources.kpi.pending")}
        value={fmt(data?.waiting ?? 0)}
        helper={t("sources.kpi.pending_help")}
      />
      <SourceSummaryCard
        tone="pink"
        icon={<AlertCircle size={18} />}
        label={t("sources.kpi.failed")}
        value={fmt(data?.failed ?? 0)}
        helper={t("sources.kpi.failed_help")}
      />
      <SourceSummaryCard
        tone="neutral"
        icon={<Ban size={18} />}
        label={t("sources.kpi.skipped")}
        value={fmt(data?.skipped ?? 0)}
        helper={t("sources.kpi.skipped_help")}
      />
      <SourceSummaryCard
        tone="blue"
        icon={<RefreshCw size={18} />}
        label={t("sources.kpi.needs_refresh")}
        value={fmt(data?.needs_refresh ?? 0)}
        helper={t("sources.kpi.needs_refresh_help")}
      />
    </MetricGrid>
  );
}
