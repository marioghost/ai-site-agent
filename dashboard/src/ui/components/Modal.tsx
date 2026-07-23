import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "../utils/cn";
import { Button } from "./Button";
import { IconButton } from "./Button";

export type ModalSize = "default" | "wide" | "xl";

type Props = {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  actions?: ReactNode;
  size?: ModalSize;
  className?: string;
};

export function Modal({
  open,
  title,
  subtitle,
  children,
  onClose,
  actions,
  size = "default",
  className,
}: Props) {
  if (!open) return null;

  return (
    <div className="ds-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className={cn(
          "ds-modal",
          size === "wide" && "ds-modal--wide",
          size === "xl" && "ds-modal--xl",
          className
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ds-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="ds-modal__header">
          <div>
            <h2 id="ds-modal-title" className="ds-modal__title">
              {title}
            </h2>
            {subtitle ? <p className="ds-modal__subtitle">{subtitle}</p> : null}
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </div>
        <div className="ds-modal__body">{children}</div>
        {actions ? <div className="ds-modal__actions">{actions}</div> : null}
      </div>
    </div>
  );
}

type ConfirmProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmProps) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      actions={
        <>
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {message}
    </Modal>
  );
}
