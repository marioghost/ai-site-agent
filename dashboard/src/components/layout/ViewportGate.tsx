import { useTranslation } from "../../i18n";

/**
 * Desktop-first product: below the supported minimum width the shell becomes
 * unusable. Show an intentional notice instead of a broken layout.
 */
export const DASHBOARD_MIN_WIDTH_PX = 1024;

export default function ViewportGate() {
  const { t } = useTranslation();

  return (
    <aside className="ds-viewport-gate" aria-labelledby="ds-viewport-gate-title">
      <div className="ds-viewport-gate__card">
        <h1 id="ds-viewport-gate-title" className="ds-page-title">
          {t("shell.viewport.title")}
        </h1>
        <p className="ds-body">{t("shell.viewport.body", { width: DASHBOARD_MIN_WIDTH_PX })}</p>
        <p className="ds-caption">{t("shell.viewport.hint")}</p>
      </div>
    </aside>
  );
}
