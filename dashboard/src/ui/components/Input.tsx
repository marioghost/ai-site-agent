import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  type InputHTMLAttributes,
  type ReactElement,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { Search } from "lucide-react";
import { cn } from "../utils/cn";

type FieldProps = {
  label?: string;
  children: ReactNode;
  className?: string;
};

function stampId(node: ReactNode, id: string): ReactNode {
  if (!isValidElement(node)) return node;
  const el = node as ReactElement<{ id?: string; children?: ReactNode }>;
  const type = el.type;

  if (type === Input || type === Select) {
    return cloneElement(el, { id: el.props.id || id });
  }
  if (type === SearchInput) {
    return cloneElement(el, { id: el.props.id || id });
  }
  if (typeof type === "string" && ["input", "select", "textarea"].includes(type)) {
    return cloneElement(el, { id: el.props.id || id });
  }
  if (el.props.children) {
    return cloneElement(el, {
      children: Children.map(el.props.children, (child) => stampId(child, id)),
    });
  }
  return node;
}

export function Field({ label, children, className }: FieldProps) {
  const autoId = useId();
  const controlId = `field-${autoId.replace(/:/g, "")}`;
  return (
    <div className={cn("ds-field", className)}>
      {label ? (
        <label className="ds-field__label" htmlFor={controlId}>
          {label}
        </label>
      ) : null}
      {label ? stampId(children, controlId) : children}
    </div>
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
