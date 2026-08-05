import { useTranslation } from "../i18n";
import type { UiLanguage } from "../i18n";
import { Select } from "../ui";

type Props = {
  /** Called in addition to the default context update, e.g. to persist server-side. */
  onChange?: (lang: UiLanguage) => void;
};

export default function LanguageSwitcher({ onChange }: Props = {}) {
  const { lang, setLang, t } = useTranslation();

  const handleChange = (next: UiLanguage) => {
    setLang(next);
    onChange?.(next);
  };

  return (
    <div className="lang-switcher">
      <label htmlFor="dashboard-lang" className="sr-only">
        {t("lang.label")}
      </label>
      <Select
        id="dashboard-lang"
        className="lang-switcher__select"
        value={lang}
        onChange={(e) => handleChange(e.target.value as UiLanguage)}
        aria-label={t("lang.label")}
      >
        <option value="uk">{t("lang.uk")}</option>
        <option value="en">{t("lang.en")}</option>
      </Select>
    </div>
  );
}
