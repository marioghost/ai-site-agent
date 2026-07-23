import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import type { ProblematicQueryRow } from "../../types";
import { DataTable, SectionCard, StatusBadge, type Column } from "../../ui";
import { useTranslation } from "../../i18n";

type Props = {
  rows: ProblematicQueryRow[];
};

export default function ProblematicQueriesSection({ rows }: Props) {
  const { t } = useTranslation();

  const columns = useMemo<Column<ProblematicQueryRow>[]>(
    () => [
      {
        id: "query",
        header: t("analytics.col.query"),
        cell: (row) => <span className="ds-analytics-query">{row.query}</span>,
      },
      {
        id: "occurrences",
        header: t("analytics.col.occurrences"),
        cell: (row) => row.occurrences,
        className: "ds-table__num",
      },
      {
        id: "fallback",
        header: t("analytics.col.fallbacks"),
        cell: (row) => row.fallback_count,
        className: "ds-table__num",
      },
      {
        id: "timeout",
        header: t("analytics.col.timeouts"),
        cell: (row) => row.timeout_count,
        className: "ds-table__num",
      },
      {
        id: "retrieval",
        header: t("analytics.col.retrieval_failures"),
        cell: (row) => row.retrieval_failure_count,
        className: "ds-table__num",
      },
      {
        id: "score",
        header: t("analytics.col.avg_score"),
        cell: (row) => row.avg_retrieval_score.toFixed(3),
        className: "ds-table__num",
      },
      {
        id: "action",
        header: t("analytics.col.actions"),
        cell: (row) => (
          <Link className="ds-btn ds-btn--secondary ds-btn--sm" to={`/chat?q=${encodeURIComponent(row.query)}`}>
            <ExternalLink size={14} />
            {t("analytics.open_in_chat")}
          </Link>
        ),
      },
    ],
    [t]
  );

  return (
    <SectionCard
      title={t("analytics.problematic_queries")}
      subtitle={t("analytics.problematic_queries_hint")}
    >
      {rows.length === 0 ? (
        <StatusBadge variant="success" label={t("analytics.no_problematic")} />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          keyFn={(row) => row.query}
          emptyTitle={t("common.no_data")}
          className="ds-analytics-table"
        />
      )}
    </SectionCard>
  );
}
