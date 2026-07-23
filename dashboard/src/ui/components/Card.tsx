import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../utils/cn";

type CardVariant = "elevated" | "flat" | "ghost";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  padding?: "none" | "sm" | "md" | "lg";
  hover?: boolean;
  variant?: CardVariant;
  children: ReactNode;
};

export function Card({
  padding = "md",
  hover = false,
  variant = "elevated",
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cn(
        "ds-card",
        variant === "flat" && "ds-card--flat",
        variant === "ghost" && "ds-card--ghost",
        padding === "md" && "ds-card--padding-md",
        padding === "sm" && "ds-card--padding-sm",
        padding === "lg" && "ds-card--padding-lg",
        padding === "none" && "ds-card--padding-none",
        hover && "ds-card--hover",
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

type CardHeaderProps = {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export function CardHeader({ title, description, actions, className }: CardHeaderProps) {
  if (!title && !description && !actions) return null;
  return (
    <div className={cn("ds-card__header", className)}>
      <div>
        {title && <h3 className="ds-card__title">{title}</h3>}
        {description && <p className="ds-card__description">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("ds-card__body", className)}>{children}</div>;
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("ds-card__footer", className)}>{children}</div>;
}

type SectionCardProps = {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  flat?: boolean;
};

export function SectionCard({
  title,
  subtitle,
  actions,
  footer,
  children,
  className,
  flat = false,
}: SectionCardProps) {
  return (
    <section className={cn("ds-section-card", flat && "ds-section-card--flat", className)}>
      {(title || actions) && (
        <div className="ds-section-card__header">
          <div>
            {title && <h3 className="ds-section-card__title">{title}</h3>}
            {subtitle && <p className="ds-section-card__subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="ds-section-card__actions">{actions}</div>}
        </div>
      )}
      <div className="ds-section-card__body">{children}</div>
      {footer && <div className="ds-section-card__footer">{footer}</div>}
    </section>
  );
}
