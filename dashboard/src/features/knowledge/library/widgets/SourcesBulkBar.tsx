import { ActionToolbar, Button } from "../../../../ui";

type Props = {
  count: number;
  busy?: boolean;
  t: (key: string, vars?: Record<string, string | number>) => string;
  onReindex: () => void;
  onDelete: () => void;
  onReset: () => void;
  onClear: () => void;
};

export default function SourcesBulkBar({
  count,
  busy = false,
  t,
  onReindex,
  onDelete,
  onReset,
  onClear,
}: Props) {
  return (
    <ActionToolbar
      count={count}
      countLabel={t("sources.bulk.selected", { count })}
      onClear={onClear}
      clearLabel={t("sources.bulk.clear")}
    >
      <Button variant="secondary" size="sm" disabled={busy} onClick={onReindex}>
        {t("sources.bulk.reindex")}
      </Button>
      <Button variant="secondary" size="sm" disabled={busy} onClick={onDelete}>
        {t("sources.bulk.delete")}
      </Button>
      <Button variant="secondary" size="sm" disabled={busy} onClick={onReset}>
        {t("sources.bulk.reset")}
      </Button>
    </ActionToolbar>
  );
}
