import { cn } from "../utils/cn";

type Props = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizes?: number[];
  infoLabel: string;
  rowsLabel?: string;
  className?: string;
};

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizes = [25, 50, 100],
  infoLabel,
  rowsLabel = "Rows per page",
  className,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const pages = buildPageList(page, totalPages);

  return (
    <div className={cn("ds-pagination", className)}>
      <div className="ds-pagination__info">{infoLabel}</div>
      {onPageSizeChange && (
        <label className="ds-field" style={{ flexDirection: "row", alignItems: "center", gap: 8, width: "auto" }}>
          <span className="ds-caption">{rowsLabel}</span>
          <select
            className="ds-select"
            style={{ width: "auto" }}
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
          >
            {pageSizes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="ds-pagination__nav">
        <button
          type="button"
          className="ds-pagination__btn"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ‹
        </button>
        {pages.map((p, i) =>
          p === "…" ? (
            <span key={`e-${i}`} className="ds-caption">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              className={cn("ds-pagination__btn", p === page && "ds-pagination__btn--active")}
              onClick={() => onPageChange(p as number)}
            >
              {p}
            </button>
          )
        )}
        <button
          type="button"
          className="ds-pagination__btn"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          ›
        </button>
      </div>
    </div>
  );
}

function buildPageList(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const items: (number | "…")[] = [1];
  if (current > 3) items.push("…");
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let p = start; p <= end; p += 1) items.push(p);
  if (current < total - 2) items.push("…");
  items.push(total);
  return items;
}
