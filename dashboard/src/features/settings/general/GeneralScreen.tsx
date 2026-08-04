import LanguageSwitcher from "../../../components/LanguageSwitcher";
import { useEngineeringMode } from "../../../context/EngineeringModeContext";
import { useTranslation } from "../../../i18n";
import { PageHeader, PageLayout, SectionCard } from "../../../ui";

export default function GeneralScreen() {
  const { t } = useTranslation();
  const { enabled, setEnabled } = useEngineeringMode();

  return (
    <PageLayout>
      <PageHeader title={t("nav.general")} />
      <p className="ds-help">{t("settings.general.subtitle")}</p>
      <SectionCard title={t("lang.label")}>
        <LanguageSwitcher />
      </SectionCard>
      <SectionCard title={t("settings.general.engineering_mode")}>
        <label className="ds-checkbox">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span>{t("settings.general.engineering_mode_help")}</span>
        </label>
      </SectionCard>
    </PageLayout>
  );
}
