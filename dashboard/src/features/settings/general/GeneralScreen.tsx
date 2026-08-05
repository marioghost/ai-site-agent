import { useState } from "react";
import { updateSettings } from "../../../api/client";
import LanguageSwitcher from "../../../components/LanguageSwitcher";
import { useEngineeringMode } from "../../../context/EngineeringModeContext";
import { useTranslation } from "../../../i18n";
import type { UiLanguage } from "../../../i18n";
import { Alert, CheckboxField, PageHeader, PageLayout, SectionCard } from "../../../ui";

export default function GeneralScreen() {
  const { t } = useTranslation();
  const { enabled, setEnabled } = useEngineeringMode();
  const [error, setError] = useState<string | null>(null);

  const onLangChange = async (next: UiLanguage) => {
    setError(null);
    try {
      await updateSettings({ dashboard_language: next });
    } catch {
      setError(t("settings.error_save"));
    }
  };

  return (
    <PageLayout>
      <PageHeader title={t("nav.general")} subtitle={t("settings.general.subtitle")} />
      {error && <Alert variant="error">{error}</Alert>}
      <SectionCard title={t("lang.label")}>
        <LanguageSwitcher onChange={(next) => void onLangChange(next)} />
      </SectionCard>
      <SectionCard title={t("settings.general.engineering_mode")}>
        <CheckboxField
          label={t("settings.general.engineering_mode_help")}
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
      </SectionCard>
    </PageLayout>
  );
}
