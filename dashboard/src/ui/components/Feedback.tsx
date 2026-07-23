import { cn } from "../utils/cn";

type AlertVariant = "error" | "success" | "info" | "warning";

type Props = {
  variant?: AlertVariant;
  children: React.ReactNode;
  className?: string;
};

export function Alert({ variant = "info", children, className }: Props) {
  return <div className={cn("ds-alert", `ds-alert--${variant}`, className)}>{children}</div>;
}

/** Soft informational banner — alias for structured Alert usage. */
export function InfoBanner({
  title,
  children,
  variant = "info",
  className,
}: {
  title?: string;
  children: React.ReactNode;
  variant?: AlertVariant;
  className?: string;
}) {
  return (
    <Alert variant={variant} className={className}>
      {title && <p className="ds-alert__title">{title}</p>}
      <p className="ds-alert__message">{children}</p>
    </Alert>
  );
}

export function Toast({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("ds-toast", className)} role="status">{children}</div>;
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cn("ds-divider", className)} />;
}

export function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("ds-tag", className)}>{children}</span>;
}

export function Chip({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("ds-chip", className)}>{children}</span>;
}

export function Avatar({ initials, className }: { initials: string; className?: string }) {
  return <div className={cn("ds-avatar", className)} aria-hidden>{initials}</div>;
}
