import type { ReactNode } from "react";
import { Card } from "./Card";
import { LoadingState } from "./States";
import { EmptyState } from "./States";
import { cn } from "../utils/cn";

export type Column<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
};

type Props<T> = {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string | number;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  onRowClick?: (row: T) => void;
  activeKey?: string | number | null;
  selectable?: boolean;
  selectedKeys?: Set<string | number>;
  onToggleRow?: (key: string | number) => void;
  onToggleAll?: (checked: boolean) => void;
  toolbar?: ReactNode;
  footer?: ReactNode;
  className?: string;
};

export function DataTable<T>({
  columns,
  data,
  keyFn,
  loading = false,
  emptyTitle = "Nothing found",
  emptyDescription,
  emptyAction,
  onRowClick,
  activeKey,
  selectable = false,
  selectedKeys,
  onToggleRow,
  onToggleAll,
  toolbar,
  footer,
  className,
}: Props<T>) {
  const allSelected =
    data.length > 0 && data.every((row) => selectedKeys?.has(keyFn(row)));
  const someSelected = data.some((row) => selectedKeys?.has(keyFn(row)));

  return (
    <Card padding="none" className={cn("ds-data-table", className)}>
      {toolbar}
      <div className="ds-table-wrap">
        <table className="ds-table">
          <thead>
            <tr>
              {selectable && (
                <th className="ds-table__check">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected && !allSelected;
                    }}
                    onChange={(e) => onToggleAll?.(e.target.checked)}
                  />
                </th>
              )}
              {columns.map((col) => (
                <th key={col.id} className={col.headerClassName}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && data.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)}>
                  <LoadingState />
                </td>
              </tr>
            ) : (
              data.map((row) => {
                const key = keyFn(row);
                const active = activeKey === key;
                const checked = selectedKeys?.has(key) ?? false;
                return (
                  <tr
                    key={key}
                    className={cn(
                      "ds-table__row",
                      onRowClick && "ds-table__row--clickable",
                      active && "ds-table__row--active"
                    )}
                    onClick={() => onRowClick?.(row)}
                  >
                    {selectable && (
                      <td
                        className="ds-table__check"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggleRow?.(key)}
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td key={col.id} className={col.className}>
                        {col.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
            {!loading && data.length === 0 && (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)}>
                  <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {footer}
    </Card>
  );
}
