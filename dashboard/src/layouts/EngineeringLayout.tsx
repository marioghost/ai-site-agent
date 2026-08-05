import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "../i18n";
import { ENGINEERING_NAV } from "../lib/navConfig";

const linkStyle = {
  display: "inline-flex",
  padding: "8px 12px",
  borderRadius: "8px",
  textDecoration: "none",
  fontWeight: 600,
};

/** S006 — section nav for the 6 Engineering destinations (mirrors KnowledgeLayout). */
export default function EngineeringLayout() {
  const { t } = useTranslation();

  return (
    <>
      <nav
        aria-label={t("nav.engineering")}
        style={{
          display: "flex",
          gap: "8px",
          padding: "0 0 16px",
          flexWrap: "wrap",
        }}
      >
        {ENGINEERING_NAV.items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              ...linkStyle,
              background: isActive ? "var(--ds-color-surface-selected, #e8eefc)" : "transparent",
              color: "inherit",
            })}
          >
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
