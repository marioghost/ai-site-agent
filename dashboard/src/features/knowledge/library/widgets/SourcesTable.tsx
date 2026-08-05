import { useEffect, useMemo, useRef, useState } from "react";
import { FileText, Globe, MoreVertical } from "lucide-react";
import type { Source } from "../../../../types";
import { DataTable, IconButton, type Column } from "../../../../ui";
import {
  displayStatusKey,
  formatDateTime,
  sourceTypeKey,
} from "./sourceUtils";
import SourceStatusPill from "./SourceStatusPill";

type MenuAction = "reindex" | "open" | "copy" | "delete" | "details";

type Props = {
  sources: Source[];
  selected: Set<number>;
  loading?: boolean;
  lang: string;
  t: (key: string, vars?: Record<string, string | number>) => string;
  activeId: number | null;
  toolbar?: React.ReactNode;
  onToggle: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
  onRowClick: (source: Source) => void;
  onMenuAction: (action: MenuAction, source: Source) => void;
};

export default function SourcesTable({
  sources,
  selected,
  loading = false,
  lang,
  t,
  activeId,
  toolbar,
  onToggle,
  onToggleAll,
  onRowClick,
  onMenuAction,
}: Props) {
  const columns = useMemo<Column<Source>[]>(
    () => [
      {
        id: "title",
        header: t("sources.col.title_url"),
        cell: (source) => (
          <div className="ds-table__cell-stack">
            <div className="ds-table__cell-title">{source.title || t("common.dash")}</div>
            <div className="ds-table__cell-sub">{source.url}</div>
          </div>
        ),
      },
      {
        id: "type",
        header: t("sources.col.type"),
        cell: (source) => {
          const typeKey = sourceTypeKey(source);
          const TypeIcon = typeKey === "page" ? Globe : FileText;
          return (
            <span className="ds-table__cell-type">
              <TypeIcon size={15} />
              {t(`sources.type.${typeKey}` as "sources.type.page")}
            </span>
          );
        },
      },
      {
        id: "status",
        header: t("sources.col.status"),
        cell: (source) => {
          const statusKey = displayStatusKey(source.display_status);
          return (
            <SourceStatusPill
              status={source.display_status}
              label={t(`sources.display.${statusKey}`)}
            />
          );
        },
      },
      {
        id: "indexed_at",
        header: t("sources.col.indexed_at"),
        className: "ds-table__cell-muted",
        cell: (source) => formatDateTime(source.indexed_at, lang),
      },
      {
        id: "chunks",
        header: t("sources.col.chunks"),
        className: "ds-table__cell-muted",
        cell: (source) => source.chunk_count ?? 0,
      },
      {
        id: "actions",
        header: t("sources.col.actions"),
        headerClassName: "ds-table__cell-actions",
        className: "ds-table__cell-actions",
        cell: (source) => (
          <RowMenu t={t} onMenuAction={(action) => onMenuAction(action, source)} />
        ),
      },
    ],
    [lang, t, onMenuAction]
  );

  return (
    <DataTable
      columns={columns}
      data={sources}
      keyFn={(s) => s.id}
      loading={loading}
      emptyTitle={t("sources.empty")}
      onRowClick={onRowClick}
      activeKey={activeId}
      selectable
      selectedKeys={selected}
      onToggleRow={(key) => onToggle(key as number)}
      onToggleAll={onToggleAll}
      toolbar={toolbar}
    />
  );
}

function RowMenu({
  t,
  onMenuAction,
}: {
  t: Props["t"];
  onMenuAction: (action: MenuAction) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const items: [MenuAction, string][] = [
    ["reindex", "sources.menu.reindex"],
    ["open", "sources.menu.open_url"],
    ["copy", "sources.menu.copy_url"],
    ["details", "sources.menu.view_details"],
    ["delete", "sources.menu.delete"],
  ];

  return (
    <div className="ds-dropdown-menu" ref={ref} onClick={(e) => e.stopPropagation()}>
      <IconButton label={t("sources.col.actions")} onClick={() => setOpen((v) => !v)}>
        <MoreVertical size={18} />
      </IconButton>
      {open && (
        <div className="ds-dropdown-menu__panel">
          {items.map(([action, labelKey]) => (
            <button
              key={action}
              type="button"
              className={`ds-dropdown-menu__item${action === "delete" ? " ds-dropdown-menu__item--danger" : ""}`}
              onClick={() => {
                setOpen(false);
                onMenuAction(action);
              }}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export type { MenuAction };
