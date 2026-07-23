import type { ReactNode } from "react";
import { cn } from "../utils/cn";

type Props = {
  children: ReactNode;
  className?: string;
};

export function PageLayout({ children, className }: Props) {
  return <div className={cn("ds-page", className)}>{children}</div>;
}

export function AppShell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("ds-shell", className)}>{children}</div>;
}

export function AppMain({ children }: { children: ReactNode }) {
  return <div className="ds-main">{children}</div>;
}

export function AppContent({ children, className }: Props) {
  return <main className={cn("ds-content", className)}>{children}</main>;
}
