import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

type Variant = "primary" | "default" | "danger" | "ghost";
type Size = "sm" | "md";

const BASE =
  "inline-flex select-none items-center justify-center gap-1.5 rounded-md border text-sm font-medium " +
  "transition-colors disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none";

const VARIANT: Record<Variant, string> = {
  primary:
    "border-transparent bg-accent text-accent-fg shadow-xs hover:bg-accent-hover active:bg-accent-active",
  default:
    "border-border bg-surface text-ink-secondary shadow-xs hover:border-border-strong hover:text-ink",
  danger:
    "border-danger-border bg-danger-subtle text-danger-subtle-fg hover:border-danger",
  ghost:
    "border-transparent bg-transparent text-ink-secondary hover:bg-surface-hover hover:text-ink",
};

const SIZE: Record<Size, string> = {
  sm: "h-8 px-2.5",
  md: "min-h-control px-3.5",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function buttonClass(variant: Variant = "default", size: Size = "md", extra?: string) {
  return cn(BASE, VARIANT[variant], SIZE[size], extra);
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", size = "md", className, type = "button", ...rest },
  ref,
) {
  return <button ref={ref} type={type} className={buttonClass(variant, size, className)} {...rest} />;
});
