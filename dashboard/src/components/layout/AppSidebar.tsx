import { useState } from "react";
import { Moon, Sun, Bot } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useEngineeringMode } from "../../context/EngineeringModeContext";
import { useSidebar } from "../../context/SidebarContext";
import { useTranslation } from "../../i18n";
import { buildNavEntries } from "../../lib/navConfig";
import { canAccessRoute } from "../../lib/permissions";
import { resetEngineeringModeOff } from "../../lib/engineeringModeStorage";
import { Avatar, NavigationItem, Sidebar, useTheme } from "../../ui";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (name[0] ?? "A").toUpperCase();
}

export default function AppSidebar() {
  const { t } = useTranslation();
  const { user, logout, hasRole } = useAuth();
  const { enabled: engineeringModeOn } = useEngineeringMode();
  const { mode, toggleMode } = useTheme();
  const { collapsed } = useSidebar();
  const [menuOpen, setMenuOpen] = useState(false);

  const role = user?.role;
  const navEntries = buildNavEntries(engineeringModeOn && hasRole("admin"));

  async function onLogout() {
    setMenuOpen(false);
    resetEngineeringModeOff();
    await logout();
    window.location.href = "/login";
  }

  const themeLabel = mode === "light" ? t("app.light_theme") : t("app.dark_theme");
  const ThemeIcon = mode === "light" ? Sun : Moon;

  return (
    <Sidebar
      collapsed={collapsed}
      brandIcon={<Bot size={22} strokeWidth={1.75} />}
      brandLabel={t("app.brand")}
      footer={
        <>
          <button
            type="button"
            className={cnNav(collapsed)}
            title={collapsed ? themeLabel : undefined}
            onClick={toggleMode}
          >
            <ThemeIcon size={18} strokeWidth={1.75} />
            {!collapsed && <span>{themeLabel}</span>}
          </button>
          {user && (
            <div className="ds-sidebar__user-wrap">
              <button
                type="button"
                className={cnNav(collapsed)}
                title={collapsed ? user.display_name || user.username : undefined}
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
              >
                <Avatar initials={initials(user.display_name || user.username)} />
                {!collapsed && (
                  <span className="ds-sidebar__user-inline">
                    <span className="ds-sidebar__user-name">
                      {user.display_name || t("app.administrator")}
                    </span>
                    <span className="ds-sidebar__user-role">
                      {hasRole("admin")
                        ? user.username
                        : t(`users.role.${user.role}` as "users.role.admin")}
                    </span>
                  </span>
                )}
              </button>
              {menuOpen && (
                <div className="ds-sidebar__user-menu">
                  <button type="button" className="ds-menu__item" disabled>
                    {t("auth.profile")}
                  </button>
                  <button
                    type="button"
                    className="ds-menu__item"
                    onClick={() => void onLogout()}
                  >
                    {t("auth.log_out")}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      }
    >
      {navEntries.map((entry) => {
        if (entry.kind === "item") {
          if (!role || !canAccessRoute(role, entry.to)) return null;
          const { to, labelKey, Icon } = entry;
          return (
            <NavigationItem
              key={to}
              to={to}
              collapsed={collapsed}
              icon={<Icon size={18} strokeWidth={1.75} />}
              label={t(labelKey)}
            />
          );
        }

        const visibleItems = entry.items.filter(
          (item) => role && canAccessRoute(role, item.to)
        );
        if (visibleItems.length === 0) return null;

        return (
          <div key={entry.labelKey} className="ds-sidebar__section">
            {!collapsed ? (
              <div className="ds-sidebar__section-label">{t(entry.labelKey)}</div>
            ) : null}
            {visibleItems.map(({ to, labelKey, Icon }) => (
              <NavigationItem
                key={`${entry.labelKey}-${to}`}
                to={to}
                collapsed={collapsed}
                icon={<Icon size={18} strokeWidth={1.75} />}
                label={t(labelKey)}
              />
            ))}
          </div>
        );
      })}
    </Sidebar>
  );
}

function cnNav(collapsed: boolean) {
  return collapsed ? "ds-nav-item ds-nav-item--collapsed" : "ds-nav-item ds-sidebar__footer-btn";
}
