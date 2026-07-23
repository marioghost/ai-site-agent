import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { Search } from "lucide-react";
import { cn } from "../utils/cn";

type FieldProps = {
  label?: string;
  children: ReactNode;
  className?: string;
};

export function Field({ label, children, className }: FieldProps) {
  return (
    <label className={cn("ds-field", className)}>
      {label && <span className="ds-field__label">{label}</span>}
      {children}
    </label>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("ds-input", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("ds-select", className)} {...rest}>
      {children}
    </select>
  );
}

type SearchProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

export function SearchInput({ className, ...rest }: SearchProps) {
  return (
    <div className="ds-search-input">
      <Search size={16} className="ds-search-input__icon" aria-hidden />
      <Input type="search" className={className} {...rest} />
    </div>
  );
}

/** @deprecated Use Select — alias for dropdown filter controls */
export const Dropdown = Select;
