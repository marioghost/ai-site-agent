import type { ReactNode } from "react";
import type { ScanMode, Settings } from "../../../../types";
import {
  CheckboxField,
  Field,
  FormGrid,
  FormStack,
  Input,
  SectionCard,
} from "../../../../ui";
import IndexingScanModeCards from "./IndexingScanModeCards";

const FILE_TYPES = ["pdf", "docx", "txt"] as const;

type Props = {
  settings: Settings;
  update: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  showAdvanced: boolean;
  onToggleAdvanced: (open: boolean) => void;
  actions: ReactNode;
  t: (key: string) => string;
};

export default function IndexingConfigCard({
  settings,
  update,
  showAdvanced,
  onToggleAdvanced,
  actions,
  t,
}: Props) {
  const filesDisabled = settings.scan_mode === "pages_only";

  const toggleFileType = (value: string, checked: boolean) => {
    const set = new Set(settings.allowed_file_types);
    if (checked) set.add(value);
    else set.delete(value);
    update("allowed_file_types", Array.from(set));
  };

  return (
    <SectionCard title={t("indexing.setup.title")}>
      <div className="ds-index-config">
        <div className="ds-index-config__col">
          <FormStack>
            <Field label={t("indexing.site_url")}>
              <Input
                value={settings.site_url || ""}
                onChange={(e) => update("site_url", e.target.value)}
                placeholder="https://example.com"
              />
            </Field>
            <Field label={t("indexing.sitemap_url")}>
              <Input
                value={settings.sitemap_url || ""}
                onChange={(e) => update("sitemap_url", e.target.value)}
                placeholder="https://example.com/sitemap.xml"
              />
            </Field>
            <CheckboxField
              label={t("indexing.scope.scan_all_pages")}
              checked={settings.scan_all_pages}
              onChange={(e) => update("scan_all_pages", e.target.checked)}
            />
            <Field label={t("indexing.scope.max_pages")}>
              <Input
                type="number"
                min={0}
                disabled={settings.scan_all_pages}
                value={settings.max_pages_per_run}
                onChange={(e) => update("max_pages_per_run", Number(e.target.value))}
              />
            </Field>
            <CheckboxField
              label={t("indexing.setup.advanced_toggle")}
              checked={showAdvanced}
              onChange={(e) => onToggleAdvanced(e.target.checked)}
            />
            {showAdvanced && (
              <FormStack>
                <FormGrid columns={1}>
                  <Field label={t("indexing.crawl_depth")}>
                    <Input
                      type="number"
                      value={settings.crawl_depth}
                      onChange={(e) => update("crawl_depth", Number(e.target.value))}
                    />
                  </Field>
                  <Field label={t("indexing.allowed_domains")}>
                    <Input
                      value={settings.allowed_domains.join(", ")}
                      onChange={(e) =>
                        update(
                          "allowed_domains",
                          e.target.value
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean)
                        )
                      }
                    />
                  </Field>
                  <Field label={t("indexing.deny_patterns")}>
                    <Input
                      value={settings.deny_url_patterns.join(", ")}
                      onChange={(e) =>
                        update(
                          "deny_url_patterns",
                          e.target.value
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean)
                        )
                      }
                    />
                  </Field>
                  <Field label={t("indexing.scope.page_refresh_hours")}>
                    <Input
                      type="number"
                      min={1}
                      value={settings.indexed_page_refresh_interval_hours}
                      onChange={(e) =>
                        update("indexed_page_refresh_interval_hours", Number(e.target.value))
                      }
                    />
                  </Field>
                  {!filesDisabled && (
                    <>
                      <CheckboxField
                        label={t("indexing.files.enable")}
                        checked={settings.enable_file_indexing}
                        onChange={(e) => update("enable_file_indexing", e.target.checked)}
                      />
                      {FILE_TYPES.map((ft) => (
                        <CheckboxField
                          key={ft}
                          label={ft.toUpperCase()}
                          disabled={!settings.enable_file_indexing}
                          checked={settings.allowed_file_types.includes(ft)}
                          onChange={(e) => toggleFileType(ft, e.target.checked)}
                        />
                      ))}
                      <Field label={t("indexing.scope.max_files")}>
                        <Input
                          type="number"
                          min={0}
                          disabled={settings.scan_all_files || filesDisabled}
                          value={settings.max_files_per_run}
                          onChange={(e) => update("max_files_per_run", Number(e.target.value))}
                        />
                      </Field>
                    </>
                  )}
                </FormGrid>
              </FormStack>
            )}
          </FormStack>
        </div>
        <div className="ds-index-config__col">
          <h4 className="ds-h3">{t("indexing.what_to_scan")}</h4>
          <IndexingScanModeCards
            settings={settings}
            onChange={(mode: ScanMode) => update("scan_mode", mode)}
            t={t}
          />
        </div>
      </div>
      {actions}
    </SectionCard>
  );
}
