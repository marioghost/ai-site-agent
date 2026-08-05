import { useTranslation } from "../../../../i18n";
import { Alert } from "../../../../ui";

export default function KnowledgeProfileLegacyBanner() {
  const { t } = useTranslation();

  return (
    <Alert variant="info" className="ds-kp-legacy-banner">
      <div className="ds-alert__content">
        <p className="ds-alert__title">{t("knowledge_profile.legacy_banner.title")}</p>
        <div className="ds-alert__message">
          <p>{t("knowledge_profile.legacy_banner.intro")}</p>
          <ul className="ds-kp-legacy-banner__list">
            <li>{t("knowledge_profile.legacy_banner.available")}</li>
            <li>{t("knowledge_profile.legacy_banner.future")}</li>
            <li>{t("knowledge_profile.legacy_banner.guidance")}</li>
          </ul>
        </div>
      </div>
    </Alert>
  );
}
