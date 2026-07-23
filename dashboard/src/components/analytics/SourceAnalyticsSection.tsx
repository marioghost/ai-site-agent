import { useMemo } from "react";
import type { SourceAnalyticsPayload } from "../../types";
import { DataTable, SectionCard, type Column } from "../../ui";
import { useTranslation } from "../../i18n";

type Props = {
  data: SourceAnalyticsPayload;
};

export default function SourceAnalyticsSection({ data }: Props) {
  const { t } = useTranslation();

  const topColumns = useMemo(
    () => [
      {
        id: "title",
        header: t("analytics.col.page"),
        cell: (row: (typeof data.top_pages)[0]) => (
          <a href={row.url} target="_blank" rel="noreferrer">
            {row.title}
          </a>
        ),
      },
      {
        id: "usage",
        header: t("analytics.col.usage"),
        cell: (row: (typeof data.top_pages)[0]) => row.usage_count,
        className: "ds-table__num",
      },
      {
        id: "score",
        header: t("analytics.col.avg_score"),
        cell: (row: (typeof data.top_pages)[0]) => row.avg_score.toFixed(3),
        className: "ds-table__num",
      },
      {
        id: "last",
        header: t("analytics.col.last_used"),
        cell: (row: (typeof data.top_pages)[0]) =>
          row.last_used_at ? new Date(row.last_used_at).toLocaleString() : "—",
      },
    ],
    [data.top_pages, t]
  );

  const unusedColumns = useMemo<Column<(typeof data.unused_sources)[0]>[]>(
    () => [
      {
        id: "title",
        header: t("analytics.col.page"),
        cell: (row) => (
          <a href={row.url} target="_blank" rel="noreferrer">
            {row.title}
          </a>
        ),
      },
      {
        id: "type",
        header: t("analytics.col.doc_type"),
        cell: (row) => row.document_type,
      },
      {
        id: "indexed",
        header: t("analytics.col.indexed_at"),
        cell: (row) => (row.indexed_at ? new Date(row.indexed_at).toLocaleDateString() : "—"),
      },
    ],
    [t]
  );

  return (
    <div className="an-tables-row">
      <SectionCard title={t("analytics.top_pages")} subtitle={t("analytics.top_pages_hint")}>
        <DataTable
          columns={topColumns}
          data={data.top_pages}
          keyFn={(row) => row.url}
          emptyTitle={t("common.no_data")}
        />
      </SectionCard>
      <SectionCard title={t("analytics.unused_sources")} subtitle={t("analytics.unused_sources_hint")}>
        <DataTable
          columns={unusedColumns}
          data={data.unused_sources}
          keyFn={(row) => row.url}
          emptyTitle={t("analytics.no_unused_sources")}
        />
      </SectionCard>
    </div>
  );
}
