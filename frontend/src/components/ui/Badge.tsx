import type { ReactNode } from "react";
import { cn } from "./cn";

export type BadgeTone =
  | "accent"
  | "success"
  | "warning"
  | "info"
  | "neutral"
  | "danger";

const SOFT: Record<BadgeTone, string> = {
  accent: "bg-accent-subtle text-accent-subtle-fg ring-accent-border",
  success: "bg-success-subtle text-success-subtle-fg ring-success-border",
  warning: "bg-warning-subtle text-warning-subtle-fg ring-warning-border",
  info: "bg-info-subtle text-info-subtle-fg ring-info-border",
  neutral: "bg-neutral-subtle text-neutral-subtle-fg ring-neutral-border",
  danger: "bg-danger-subtle text-danger-subtle-fg ring-danger-border",
};

const OUTLINE: Record<BadgeTone, string> = {
  accent: "text-accent-subtle-fg ring-accent-border",
  success: "text-success-subtle-fg ring-success-border",
  warning: "text-warning-subtle-fg ring-warning-border",
  info: "text-info-subtle-fg ring-info-border",
  neutral: "text-ink-secondary ring-neutral-border",
  danger: "text-danger-subtle-fg ring-danger-border",
};

const DOT: Record<BadgeTone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  info: "bg-info",
  neutral: "bg-ink-muted",
  danger: "bg-danger",
};

export function Badge({
  tone = "neutral",
  variant = "soft",
  dot = false,
  mono = false,
  uppercase = false,
  className,
  children,
}: {
  tone?: BadgeTone;
  variant?: "soft" | "outline";
  dot?: boolean;
  mono?: boolean;
  uppercase?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-2xs font-semibold ring-1 ring-inset",
        uppercase && "uppercase tracking-wide",
        mono && "font-mono",
        variant === "soft" ? SOFT[tone] : OUTLINE[tone],
        className,
      )}
    >
      {dot && <span aria-hidden="true" className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOT[tone])} />}
      {children}
    </span>
  );
}
