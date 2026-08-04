import { PageHeader, PageLayout } from "../../ui";
import { useTranslation } from "../../i18n";

/** S001 Q3 — neutral scaffold only. */
export default function MigrationPlaceholder({ titleKey }: { titleKey?: string }) {
  const { t } = useTranslation();
  const title = titleKey ? t(titleKey) : t("app.brand");
  return (
    <PageLayout>
      <PageHeader title={title} />
      <p className="ds-help">{t("scaffold.not_migrated")}</p>
    </PageLayout>
  );
}
