import type { ReactNode } from "react";

interface Props {
  variant: "primary" | "secondary" | "analytics";
  children: ReactNode;
}

export default function OverviewGrid({ variant, children }: Props) {
  return <div className={`overview-grid overview-grid--${variant}`}>{children}</div>;
}
