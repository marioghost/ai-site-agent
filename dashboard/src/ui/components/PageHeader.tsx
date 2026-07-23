import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { cn } from "../utils/cn";
import { IconButton } from "./Button";

type Props = {
  title: string;
  subtitle?: string;
  breadcrumbs?: ReactNode;
  actions?: ReactNode;
  status?: ReactNode;
  onRefresh?: () => void;
  refreshDisabled?: boolean;
  className?: string;
};

export function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
  status,
  onRefresh,
  refreshDisabled,
  className,
}: Props) {
  return (
    <header className={cn("ds-page-header", className)}>
      <div className="ds-page-header__content">
        {breadcrumbs && <div className="ds-page-header__breadcrumb">{breadcrumbs}</div>}
        <div className="ds-page-header__title-row">
          <h1 className="ds-page-header__title">{title}</h1>
          {status}
        </div>
        {subtitle && <p className="ds-page-header__subtitle">{subtitle}</p>}
      </div>
      {(actions || onRefresh) && (
        <div className="ds-page-header__actions">
          {onRefresh && (
            <IconButton label="Refresh" onClick={onRefresh} disabled={refreshDisabled}>
              <RefreshCw size={16} strokeWidth={1.75} />
            </IconButton>
          )}
          {actions}
        </div>
      )}
    </header>
  );
}

type SectionProps = {
  title?: string;
  description?: string;
  actions?: ReactNode;
  divider?: boolean;
  children: ReactNode;
  className?: string;
};

/** Whitespace-first section — no card chrome unless content needs elevation. */
export function Section({
  title,
  description,
  actions,
  divider = true,
  children,
  className,
}: SectionProps) {
  return (
    <section className={cn("ds-section", className)}>
      {(title || actions) && (
        <div className={cn("ds-section__header", !divider && "ds-section__header--plain")}>
          <div>
            {title && <h2 className="ds-section__title">{title}</h2>}
            {description && <p className="ds-section__description">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className="ds-section__body">{children}</div>
    </section>
  );
}

/** @deprecated use Section */
export function PageSection({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <Section title={title} className={className}>
      {children}
    </Section>
  );
}
