import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { IconButton } from "./Button";
import { cn } from "../utils/cn";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  mode?: "overlay" | "inline";
  closeLabel?: string;
};

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  mode = "overlay",
  closeLabel = "Close",
}: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {mode === "overlay" && (
        <button type="button" className="ds-drawer-backdrop" aria-label={closeLabel} onClick={onClose} />
      )}
      <aside className={cn("ds-drawer", mode === "inline" && "ds-drawer--inline")}>
        <div className="ds-drawer__header">
          <h2 className="ds-h3">{title}</h2>
          <IconButton label={closeLabel} onClick={onClose}>
            <X size={18} />
          </IconButton>
        </div>
        <div className="ds-drawer__body">{children}</div>
        {footer && <div className="ds-drawer__footer">{footer}</div>}
      </aside>
    </>
  );
}
