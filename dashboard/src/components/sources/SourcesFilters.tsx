import { ChevronDown, ChevronUp } from "lucide-react";
import { Button, Field, FilterBar, Input, SearchInput, Select } from "../../ui";

export type SourceFilterValues = {
  search: string;
  bucket: string;
  source_type: string;
  date_range: string;
  url_contains: string;
};

export const EMPTY_FILTERS: SourceFilterValues = {
  search: "",
  bucket: "",
  source_type: "",
  date_range: "",
  url_contains: "",
};

type Props = {
  values: SourceFilterValues;
  collapsed: boolean;
  t: (key: string) => string;
  onChange: (patch: Partial<SourceFilterValues>) => void;
  onReset: () => void;
  onToggleCollapse: () => void;
};

export default function SourcesFilters({
  values,
  collapsed,
  t,
  onChange,
  onReset,
  onToggleCollapse,
}: Props) {
  return (
    <FilterBar
      elevated
      collapsed={collapsed}
      collapseLabel={
        collapsed ? (
          <>
            {t("sources.filter.show")} <ChevronDown size={16} />
          </>
        ) : (
          <>
            {t("sources.filter.hide")} <ChevronUp size={16} />
          </>
        )
      }
      onToggleCollapse={onToggleCollapse}
      actions={
        !collapsed ? (
          <Button variant="ghost" size="sm" onClick={onReset}>
            {t("sources.filter.reset")}
          </Button>
        ) : undefined
      }
    >
      {!collapsed && (
        <>
          <Field label={t("sources.filter.search")}>
            <SearchInput
              value={values.search}
              placeholder={t("sources.filter.search_placeholder")}
              onChange={(e) => onChange({ search: e.target.value })}
            />
          </Field>

          <Field label={t("sources.filter.status")}>
            <Select value={values.bucket} onChange={(e) => onChange({ bucket: e.target.value })}>
              <option value="">{t("sources.filter.all_status")}</option>
              <option value="ready">{t("sources.display.ready")}</option>
              <option value="pending">{t("sources.display.pending")}</option>
              <option value="failed">{t("sources.display.failed")}</option>
              <option value="skipped">{t("sources.display.skipped")}</option>
              <option value="needs_refresh">{t("sources.display.needs_refresh")}</option>
            </Select>
          </Field>

          <Field label={t("sources.filter.type")}>
            <Select
              value={values.source_type}
              onChange={(e) => onChange({ source_type: e.target.value })}
            >
              <option value="">{t("sources.filter.all_types")}</option>
              <option value="page">{t("sources.type.page")}</option>
              <option value="file">{t("sources.type.file")}</option>
              <option value="pdf">{t("sources.type.pdf")}</option>
              <option value="docx">{t("sources.type.docx")}</option>
              <option value="txt">{t("sources.type.txt")}</option>
            </Select>
          </Field>

          <Field label={t("sources.filter.date")}>
            <Select
              value={values.date_range}
              onChange={(e) => onChange({ date_range: e.target.value })}
            >
              <option value="">{t("sources.filter.anytime")}</option>
              <option value="today">{t("sources.filter.today")}</option>
              <option value="week">{t("sources.filter.week")}</option>
              <option value="month">{t("sources.filter.month")}</option>
            </Select>
          </Field>

          <Field label={t("sources.filter.url_contains")}>
            <Input
              type="text"
              value={values.url_contains}
              placeholder={t("sources.filter.url_placeholder")}
              onChange={(e) => onChange({ url_contains: e.target.value })}
            />
          </Field>
        </>
      )}
    </FilterBar>
  );
}
