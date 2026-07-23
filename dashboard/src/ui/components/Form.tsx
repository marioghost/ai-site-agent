import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { cn } from "../utils/cn";

type GridProps = {
  children: ReactNode;
  columns?: 1 | 2 | 3 | 4;
  className?: string;
};

export function FormGrid({ children, columns = 2, className }: GridProps) {
  return (
    <div className={cn("ds-form-grid", `ds-form-grid--${columns}`, className)}>
      {children}
    </div>
  );
}

export function HelpText({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("ds-field__hint", className)}>{children}</p>;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("ds-textarea", className)} {...rest} />;
}

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
};

export function CheckboxField({ label, className, id, ...rest }: CheckboxProps) {
  const inputId = id ?? (typeof label === "string" ? `cb-${label.slice(0, 24)}` : undefined);
  return (
    <label className={cn("ds-checkbox-field", className)} htmlFor={inputId}>
      <input type="checkbox" className="ds-checkbox-field__input" id={inputId} {...rest} />
      <span className="ds-checkbox-field__label">{label}</span>
    </label>
  );
}

type SwitchProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
};

export function SwitchField({ label, className, id, ...rest }: SwitchProps) {
  const inputId = id ?? (typeof label === "string" ? `sw-${label.slice(0, 24)}` : undefined);
  return (
    <label className={cn("ds-switch-field", className)} htmlFor={inputId}>
      <span className="ds-switch-field__label">{label}</span>
      <input
        type="checkbox"
        role="switch"
        className="ds-switch-field__input"
        id={inputId}
        {...rest}
      />
      <span className="ds-switch" aria-hidden="true" />
    </label>
  );
}

type StackProps = { children: ReactNode; className?: string };

export function FormStack({ children, className }: StackProps) {
  return <div className={cn("ds-form-stack", className)}>{children}</div>;
}
