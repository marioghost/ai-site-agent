import { Pagination } from "../../ui";

type Props = {
  page: number;
  pageSize: number;
  total: number;
  lang: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

export default function SourcesPagination({
  page,
  pageSize,
  total,
  lang,
  t,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page, totalPages) * pageSize;
  const clampedTo = Math.min(to, total);

  const fmt = (n: number) =>
    new Intl.NumberFormat(lang === "uk" ? "uk-UA" : "en-US").format(n);

  return (
    <Pagination
      page={page}
      pageSize={pageSize}
      total={total}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      infoLabel={t("sources.pagination.showing", {
        from: fmt(from),
        to: fmt(clampedTo),
        total: fmt(total),
      })}
      rowsLabel={t("sources.pagination.rows")}
    />
  );
}
