import type { ReactNode } from "react";
import { Button } from "./Button";
import { cn } from "../utils/cn";

type Props = {
  count: number;
  countLabel: string;
  children: ReactNode;
  onClear?: () => void;
  clearLabel?: string;
  className?: string;
};

export function ActionToolbar({
  count,
  countLabel,
  children,
  onClear,
  clearLabel = "Clear",
  className,
}: Props) {
  if (count <= 0) return null;

  return (
    <div className={cn("ds-action-toolbar", className)}>
      <span className="ds-action-toolbar__count">{countLabel}</span>
      <div className="ds-action-toolbar__actions">
        {children}
        {onClear && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            {clearLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
