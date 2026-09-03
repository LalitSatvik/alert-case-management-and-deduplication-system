import type { ReactNode } from "react";
import { Sparkline } from "./Sparkline";
import { cn } from "./cn";

/** Big number card with an icon and a decorative trend line — the references' KPI style. */
export function StatCard({
  icon,
  label,
  value,
  delta,
  seed = 0,
  tone = "accent",
  className,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  delta?: { value: string; positive: boolean };
  seed?: number;
  tone?: "accent" | "info" | "success" | "danger";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 shadow-xs",
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-sunken text-ink-secondary">
          {icon}
        </span>
        <Sparkline seed={seed} tone={tone} />
      </div>
      <div>
        <p className="text-xs font-medium text-ink-tertiary">{label}</p>
        <div className="mt-0.5 flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums text-ink">{value}</span>
          {delta && (
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-2xs font-medium",
                delta.positive
                  ? "bg-success-subtle text-success-subtle-fg"
                  : "bg-danger-subtle text-danger-subtle-fg",
              )}
            >
              {delta.value}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
