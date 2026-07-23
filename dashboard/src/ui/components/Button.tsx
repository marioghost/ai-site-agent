import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../utils/cn";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={cn(
        "ds-btn",
        `ds-btn--${variant}`,
        size !== "md" && `ds-btn--${size}`,
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

type IconBtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  label: string;
};

export function IconButton({ children, label, className, ...rest }: IconBtnProps) {
  return (
    <button type="button" className={cn("ds-icon-btn", className)} aria-label={label} {...rest}>
      {children}
    </button>
  );
}
