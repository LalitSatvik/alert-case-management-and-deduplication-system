import { useState } from "react";
import type { TimelineEntry } from "../../api/types";
import { relativeTime } from "../../lib/format";
import { FieldLabel } from "../ui/Field";
import { cn } from "../ui/cn";

interface Step {
  seq: number;
  kind: "status" | "assign";
  label: string;
  actor: string;
  at: string;
  detail?: string;
}

function buildSteps(timeline: TimelineEntry[]): Step[] {
  return [...(timeline ?? [])]
    .filter((e) => e.action === "case.transitioned" || e.action === "case.assigned")
    .sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
    .map((e) => {
      const actor = e.actor_role ?? e.actor_id ?? "system";
      if (e.action === "case.assigned") {
        const to = (e.after?.assignee_id as string | null) ?? null;
        return {
          seq: e.seq,
          kind: "assign" as const,
          label: to ? "Assigned" : "Unassigned",
          actor,
          at: e.created_at,
          detail: e.reason ?? undefined,
        };
      }
      const status = (e.after?.status as string) ?? "?";
      const disposition = e.after?.disposition as string | null;
      return {
        seq: e.seq,
        kind: "status" as const,
        label: status,
        actor,
        at: e.created_at,
        detail: [disposition, e.reason].filter(Boolean).join(" · ") || undefined,
      };
    });
}

export function StatusHistory({ timeline }: { timeline: TimelineEntry[] }) {
  const steps = buildSteps(timeline);
  const [open, setOpen] = useState<number | null>(null);

  if (steps.length === 0) {
    return (
      <div>
        <FieldLabel>History</FieldLabel>
        <p className="mt-1 text-xs text-ink-tertiary">No transitions yet.</p>
      </div>
    );
  }

  return (
    <div>
      <FieldLabel>History</FieldLabel>
      <ol className="relative mt-1.5 space-y-1 before:absolute before:bottom-2 before:left-[5px] before:top-2 before:w-px before:bg-border">
        {steps.map((s, i) => {
          const current = i === steps.length - 1;
          const expandable = Boolean(s.detail);
          return (
            <li key={s.seq} className="relative pl-4">
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-0 top-[5px] h-[11px] w-[11px] rounded-full border-2 border-surface",
                  current ? "bg-accent" : "bg-border-strong",
                )}
              />
              <button
                type="button"
                disabled={!expandable}
                onClick={() => setOpen(open === s.seq ? null : s.seq)}
                className={cn(
                  "flex w-full flex-col rounded-sm px-1 py-0.5 text-left",
                  expandable && "hover:bg-surface-hover",
                )}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span
                    className={cn(
                      "text-xs font-medium",
                      current ? "text-ink" : "text-ink-secondary",
                    )}
                  >
                    {s.label}
                  </span>
                  <span className="shrink-0 text-2xs text-ink-tertiary">{relativeTime(s.at)}</span>
                </span>
                <span className="font-mono text-2xs text-ink-tertiary">{s.actor}</span>
                {open === s.seq && s.detail && (
                  <span className="mt-0.5 text-2xs text-ink-secondary">{s.detail}</span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
