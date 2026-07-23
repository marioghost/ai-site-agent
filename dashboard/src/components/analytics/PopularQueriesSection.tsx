import { useMemo, useState } from "react";
import type { PopularQueryRow } from "../../types";
import { Button, DataTable, SearchInput, SectionCard, StatusBadge, type Column } from "../../ui";
import { useTranslation } from "../../i18n";

type Props = {
  rows: PopularQueryRow[];
  pct: (n: number) => string;
  msLabel: (n: number) => string;
  onSearch: (query: string) => void;
  searching?: boolean;
};

export default function PopularQueriesSection({
  rows,
  pct,
  msLabel,
  onSearch,
  searching = false,
}: Props) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");

  const columns = useMemo<Column<PopularQueryRow>[]>(
    () => [
      {
        id: "query",
        header: t("analytics.col.query"),
        cell: (row) => <span className="ds-analytics-query">{row.query}</span>,
      },
      {
        id: "count",
        header: t("analytics.col.count"),
        cell: (row) => row.count,
        className: "ds-table__num",
      },
      {
        id: "avg",
        header: t("analytics.col.avg_time"),
        cell: (row) => msLabel(row.avg_response_ms),
        className: "ds-table__num",
      },
      {
        id: "cache",
        header: t("analytics.col.cache"),
        cell: (row) => pct(row.cache_hit_rate),
        className: "ds-table__num",
      },
      {
        id: "fallback",
        header: t("analytics.col.fallbacks"),
        cell: (row) => row.fallback_count,
        className: "ds-table__num",
      },
      {
        id: "success",
        header: t("analytics.col.success_rate"),
        cell: (row) => (
          <StatusBadge
            variant={row.success_rate >= 0.7 ? "success" : row.success_rate >= 0.4 ? "warning" : "danger"}
            label={pct(row.success_rate)}
            size="sm"
          />
        ),
        className: "ds-table__num",
      },
    ],
    [msLabel, pct, t]
  );

  return (
    <SectionCard title={t("analytics.popular_queries")} subtitle={t("analytics.popular_queries_hint")}>
      <div className="ds-analytics-table-toolbar">
        <SearchInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("analytics.search_queries")}
          aria-label={t("analytics.search_queries")}
        />
        <Button
          type="button"
          variant="secondary"
          disabled={searching}
          onClick={() => onSearch(search.trim())}
        >
          {t("common.search")}
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={rows}
        keyFn={(row) => row.query}
        emptyTitle={t("common.no_data")}
        className="ds-analytics-table"
      />
    </SectionCard>
  );
}
