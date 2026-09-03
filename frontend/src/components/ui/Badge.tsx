import type { ReactNode } from "react";
import { cn } from "./cn";

export type BadgeTone = "accent" | "success" | "warning" | "info" | "neutral" | "danger";

const SOFT: Record<BadgeTone, string> = {
  accent: "bg-accent-subtle text-accent-subtle-fg",
  success: "bg-success-subtle text-success-subtle-fg",
  warning: "bg-warning-subtle text-warning-subtle-fg",
  info: "bg-info-subtle text-info-subtle-fg",
  neutral: "bg-neutral-subtle text-neutral-subtle-fg",
  danger: "bg-danger-subtle text-danger-subtle-fg",
};

const OUTLINE: Record<BadgeTone, string> = {
  accent: "text-accent-subtle-fg ring-1 ring-inset ring-accent-border",
  success: "text-success-subtle-fg ring-1 ring-inset ring-success-border",
  warning: "text-warning-subtle-fg ring-1 ring-inset ring-warning-border",
  info: "text-info-subtle-fg ring-1 ring-inset ring-info-border",
  neutral: "text-ink-secondary ring-1 ring-inset ring-neutral-border",
  danger: "text-danger-subtle-fg ring-1 ring-inset ring-danger-border",
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
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-2xs font-medium",
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
