import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "../i18n";

const linkStyle = {
  display: "inline-flex",
  padding: "8px 12px",
  borderRadius: "8px",
  textDecoration: "none",
  fontWeight: 600,
};

export default function KnowledgeLayout() {
  const { t } = useTranslation();

  return (
    <>
      <nav
        aria-label={t("nav.knowledge")}
        style={{
          display: "flex",
          gap: "8px",
          padding: "0 0 16px",
          flexWrap: "wrap",
        }}
      >
        <NavLink
          to="/knowledge/library"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.library")}
        </NavLink>
        <NavLink
          to="/knowledge/update"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.update")}
        </NavLink>
        <NavLink
          to="/knowledge/site"
          style={({ isActive }) => ({
            ...linkStyle,
            background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
            color: "inherit",
          })}
        >
          {t("nav.site")}
        </NavLink>
      </nav>
      <Outlet />
    </>
  );
}
