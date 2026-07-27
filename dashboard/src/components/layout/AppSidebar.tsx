import { useState } from "react";
import {
  BarChart3,
  Bot,
  Brain,
  FileStack,
  LayoutDashboard,
  MessageSquare,
  Moon,
  RefreshCw,
  ScrollText,
  Settings,
  Sun,
  TriangleAlert,
  Users,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useSidebar } from "../../context/SidebarContext";
import { useTranslation } from "../../i18n";
import { canAccessRoute } from "../../lib/permissions";
import { Avatar, NavigationItem, Sidebar, useTheme } from "../../ui";

const navItems = [
  { to: "/overview", key: "nav.overview", Icon: LayoutDashboard },
  { to: "/indexing", key: "nav.indexing", Icon: RefreshCw },
  { to: "/sources", key: "nav.sources", Icon: FileStack },
  { to: "/chat", key: "nav.chat_test", Icon: MessageSquare },
  { to: "/analytics", key: "nav.analytics", Icon: BarChart3 },
  { to: "/logs", key: "nav.logs", Icon: ScrollText },
  { to: "/understanding", key: "nav.understanding", Icon: TriangleAlert },
  { to: "/users", key: "nav.users", Icon: Users },
  { to: "/knowledge-profile", key: "nav.knowledge_profile", Icon: Brain },
  { to: "/settings", key: "nav.agent_settings", Icon: Settings },
] as const;

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (name[0] ?? "A").toUpperCase();
}

export default function AppSidebar() {
  const { t } = useTranslation();
  const { user, logout, hasRole } = useAuth();
  const { mode, toggleMode } = useTheme();
  const { collapsed } = useSidebar();
  const [menuOpen, setMenuOpen] = useState(false);

  const visibleNav = navItems.filter(({ to }) =>
    user ? canAccessRoute(user.role, to) : false
  );

  async function onLogout() {
    setMenuOpen(false);
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
                      {hasRole("admin") ? user.username : t(`users.role.${user.role}` as "users.role.admin")}
                    </span>
                  </span>
                )}
              </button>
              {menuOpen && (
                <div className="ds-sidebar__user-menu">
                  <button type="button" className="ds-menu__item" disabled>
                    {t("auth.profile")}
                  </button>
                  <button type="button" className="ds-menu__item" onClick={() => void onLogout()}>
                    {t("auth.log_out")}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      }
    >
      {visibleNav.map(({ to, key, Icon }) => (
        <NavigationItem
          key={to}
          to={to}
          collapsed={collapsed}
          icon={<Icon size={18} strokeWidth={1.75} />}
          label={t(key)}
        />
      ))}
    </Sidebar>
  );
}

function cnNav(collapsed: boolean) {
  return collapsed ? "ds-nav-item ds-nav-item--collapsed" : "ds-nav-item ds-sidebar__footer-btn";
}
