import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "../utils/cn";
import { Avatar } from "./Feedback";

type NavItemProps = {
  to: string;
  icon: ReactNode;
  label: string;
  collapsed?: boolean;
};

export function NavigationItem({ to, icon, label, collapsed = false }: NavItemProps) {
  return (
    <NavLink
      to={to}
      title={collapsed ? label : undefined}
      aria-label={label}
      className={({ isActive }) =>
        cn(
          "ds-nav-item",
          isActive && "ds-nav-item--active",
          collapsed && "ds-nav-item--collapsed"
        )
      }
    >
      <span className="ds-nav-item__icon">{icon}</span>
      {!collapsed && <span className="ds-nav-item__label">{label}</span>}
    </NavLink>
  );
}

type SidebarProps = {
  brand?: ReactNode;
  brandIcon?: ReactNode;
  brandLabel?: string;
  children: ReactNode;
  footer?: ReactNode;
  knowledgeCard?: ReactNode;
  collapsed?: boolean;
};

export function Sidebar({
  brand,
  brandIcon,
  brandLabel,
  children,
  footer,
  knowledgeCard,
  collapsed = false,
}: SidebarProps) {
  return (
    <aside className={cn("ds-sidebar", collapsed && "ds-sidebar--collapsed")}>
      <div>
        <div className="ds-sidebar__brand" title={collapsed ? brandLabel : undefined}>
          {brandIcon}
          {!collapsed && brandLabel && (
            <span className="ds-sidebar__brand-label">{brandLabel}</span>
          )}
          {!collapsed && !brandLabel && brand}
        </div>
        <nav className="ds-sidebar__nav">{children}</nav>
        {!collapsed && knowledgeCard}
      </div>
      {footer && (
        <div className={cn("ds-sidebar__footer", collapsed && "ds-sidebar__footer--collapsed")}>
          {footer}
        </div>
      )}
    </aside>
  );
}

export function KnowledgeMiniCard({
  title,
  percent,
  progress,
  className,
}: {
  title: string;
  percent: string;
  progress: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("ds-kb-mini", className)}>
      <div className="ds-kb-mini__content">
        <div className="ds-kb-mini__title">{title}</div>
        <div className="ds-kb-mini__percent">{percent}</div>
        {progress && <div className="ds-kb-mini__progress">{progress}</div>}
      </div>
    </div>
  );
}

type TopbarProps = {
  start?: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
};

export function Topbar({ start, context, actions }: TopbarProps) {
  return (
    <header className="ds-topbar">
      <div className="ds-topbar__start">
        {start}
        {context && <div className="ds-topbar__context">{context}</div>}
      </div>
      {actions && <div className="ds-topbar__actions">{actions}</div>}
    </header>
  );
}

export function UserMenu({
  initials,
  name,
  role,
  menu,
  collapsed = false,
}: {
  initials: string;
  name: string;
  role: string;
  menu?: ReactNode;
  collapsed?: boolean;
}) {
  return (
    <div className={cn("ds-sidebar__user", collapsed && "ds-sidebar__user--collapsed")}>
      <Avatar initials={initials} />
      {!collapsed && (
        <div className="ds-sidebar__user-text">
          <div className="ds-sidebar__user-name">{name}</div>
          <div className="ds-sidebar__user-role">{role}</div>
        </div>
      )}
      {menu}
    </div>
  );
}
