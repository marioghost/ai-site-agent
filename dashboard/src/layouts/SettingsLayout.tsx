import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "../i18n";

const linkStyle = {
  display: "inline-flex",
  padding: "8px 12px",
  borderRadius: "8px",
  textDecoration: "none",
  fontWeight: 600,
};

export default function SettingsLayout() {
  const { t } = useTranslation();

  return (
    <>
      <nav
        aria-label={t("nav.settings")}
        style={{
          display: "flex",
          gap: "8px",
          padding: "0 0 16px",
          flexWrap: "wrap",
        }}
      >
        <NavLink
          to="/settings/general"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.general")}
        </NavLink>
        <NavLink
          to="/settings/models"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.models")}
        </NavLink>
        <NavLink
          to="/settings/answers"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.answers")}
        </NavLink>
        <NavLink
          to="/settings/access"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.access")}
        </NavLink>
      </nav>
      <Outlet />
    </>
  );
}
