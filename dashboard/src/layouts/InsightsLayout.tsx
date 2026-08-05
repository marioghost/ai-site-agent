import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "../i18n";

const linkStyle = {
  display: "inline-flex",
  padding: "8px 12px",
  borderRadius: "8px",
  textDecoration: "none",
  fontWeight: 600,
};

export default function InsightsLayout() {
  const { t } = useTranslation();

  return (
    <>
      <nav
        aria-label={t("nav.insights")}
        style={{
          display: "flex",
          gap: "8px",
          padding: "0 0 16px",
          flexWrap: "wrap",
        }}
      >
        <NavLink
          to="/insights/performance"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.performance")}
        </NavLink>
        <NavLink
          to="/insights/activity"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.activity")}
        </NavLink>
      </nav>
      <Outlet />
    </>
  );
}
