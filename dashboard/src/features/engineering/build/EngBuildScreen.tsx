import { useTranslation } from "../../../i18n";
import { PageHeader, PageLayout } from "../../../ui";
import MigrationFlagsPanel from "./widgets/MigrationFlagsPanel";

/**
 * S006 (G7-P5) — Engineering owner for the build/migration flag catalog.
 * Product Settings never mounts `MigrationFlagsPanel`; it lives only here.
 */
export default function EngBuildScreen() {
  const { t } = useTranslation();

  return (
    <PageLayout className="ds-page--wide">
      <PageHeader title={t("nav.eng_build")} subtitle={t("eng.build.subtitle")} />
      <MigrationFlagsPanel />
    </PageLayout>
  );
}
