import type { TimelineEntry } from "../api/types";
import { relativeTime } from "../lib/format";

function actorOf(e: TimelineEntry): string {
  return e.actor_role ?? e.actor_id ?? "system";
}

export function DiffView({
  before,
  after,
}: {
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}) {
  if (!before && !after) return null;
  const keys = Array.from(
    new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]),
  ).filter((k) => JSON.stringify(before?.[k]) !== JSON.stringify(after?.[k]));
  if (keys.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1 rounded-md bg-surface-sunken p-2 font-mono text-xs">
      {keys.map((k) => (
        <li key={k}>
          <span className="text-ink-tertiary">{k}: </span>
          <span className="text-ink-danger line-through">{JSON.stringify(before?.[k]) ?? "—"}</span>
          <span className="mx-1 text-ink-tertiary">→</span>
          <span className="text-ink-success">{JSON.stringify(after?.[k]) ?? "—"}</span>
        </li>
      ))}
    </ul>
  );
}

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  const sorted = [...(entries ?? [])].sort((a, b) => (b.seq ?? 0) - (a.seq ?? 0));
  if (sorted.length === 0) {
    return <p className="text-sm text-ink-tertiary">No activity recorded yet.</p>;
  }
  return (
    <ol className="u-stagger relative space-y-3 before:absolute before:bottom-3 before:left-[7px] before:top-3 before:w-px before:bg-border">
      {sorted.map((e) => (
        <li key={e.seq} className="relative pl-7">
          <span
            aria-hidden="true"
            className="absolute left-0 top-3 h-[15px] w-[15px] rounded-full border-2 border-surface bg-border-strong ring-1 ring-border"
          />
          <div className="rounded-lg border border-border bg-surface p-3 shadow-xs">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-sm font-medium text-ink">{e.action}</span>
              <span className="shrink-0 text-xs text-ink-tertiary">{relativeTime(e.created_at)}</span>
            </div>
            <div className="mt-0.5 text-xs text-ink-tertiary">
              {actorOf(e)}
              {e.actor_role && e.actor_id ? ` · ${e.actor_id}` : ""}
            </div>
            {e.reason && <p className="mt-1.5 text-sm text-ink-secondary">{e.reason}</p>}
            <DiffView before={e.before} after={e.after} />
          </div>
        </li>
      ))}
    </ol>
  );
}
