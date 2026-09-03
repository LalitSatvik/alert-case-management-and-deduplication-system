import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { TimelineEntry } from "../api/types";
import { relativeTime } from "../lib/format";
import { RecordDiff } from "./ui/Diff";
import { Badge, type BadgeTone } from "./ui/Badge";
import { cn } from "./ui/cn";
import {
  clusterEntries,
  entitiesOf,
  entityKey,
  entityTypeLabel,
  type EntityKind,
  type EntityRef,
  type TimelineCluster,
} from "./timeline/entities";

const ENTITY_TONE: Record<EntityKind, BadgeTone> = {
  alert: "danger",
  note: "info",
  user: "accent",
  method: "success",
  status: "warning",
};

const ENTITY_DOT: Record<EntityKind, string> = {
  alert: "bg-danger",
  note: "bg-info",
  user: "bg-accent",
  method: "bg-success",
  status: "bg-warning",
};

function actorOf(e: TimelineEntry): string {
  return e.actor_role ?? e.actor_id ?? "system";
}

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  const clusters = useMemo(() => {
    const sorted = [...(entries ?? [])].sort((a, b) => (b.seq ?? 0) - (a.seq ?? 0));
    return clusterEntries(sorted);
  }, [entries]);

  const [open, setOpen] = useState<Set<string>>(new Set());
  const [activeEntity, setActiveEntity] = useState<string | null>(null);

  const listRef = useRef<HTMLOListElement>(null);
  const nodeRefs = useRef<Map<string, HTMLLIElement>>(new Map());
  const [bracket, setBracket] = useState<{ top: number; height: number; ticks: number[] } | null>(
    null,
  );

  // Distinct entities across the whole timeline, with occurrence counts.
  const entityIndex = useMemo(() => {
    const map = new Map<string, { ref: EntityRef; count: number; clusterKeys: Set<string> }>();
    for (const cl of clusters) {
      for (const entry of cl.entries) {
        for (const ref of entitiesOf(entry)) {
          const k = entityKey(ref);
          const hit = map.get(k) ?? { ref, count: 0, clusterKeys: new Set<string>() };
          hit.count += 1;
          hit.clusterKeys.add(cl.key);
          map.set(k, hit);
        }
      }
    }
    return map;
  }, [clusters]);

  const matchedClusterKeys = useMemo(
    () => (activeEntity ? (entityIndex.get(activeEntity)?.clusterKeys ?? new Set()) : new Set()),
    [activeEntity, entityIndex],
  );

  useLayoutEffect(() => {
    if (!activeEntity || !listRef.current) {
      setBracket(null);
      return;
    }
    const listTop = listRef.current.getBoundingClientRect().top;
    const tops: number[] = [];
    for (const cl of clusters) {
      if (!matchedClusterKeys.has(cl.key)) continue;
      const el = nodeRefs.current.get(cl.key);
      if (el) {
        const r = el.getBoundingClientRect();
        tops.push(r.top - listTop + 11);
      }
    }
    if (tops.length < 2) {
      setBracket(null);
      return;
    }
    setBracket({
      top: tops[0],
      height: tops[tops.length - 1] - tops[0],
      ticks: tops.map((t) => t - tops[0]),
    });
  }, [activeEntity, matchedClusterKeys, clusters, open]);

  if (clusters.length === 0) {
    return <p className="text-sm text-ink-tertiary">No activity recorded yet.</p>;
  }

  const toggle = (key: string) =>
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  const clickEntity = (k: string) => setActiveEntity((cur) => (cur === k ? null : k));

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <ol
        ref={listRef}
        className="relative flex-1 space-y-2 before:absolute before:bottom-3 before:left-[10px] before:top-3 before:w-px before:bg-border"
      >
        {/* entity bracket — draws on when an entity is active */}
        {bracket && (
          <div
            key={activeEntity}
            aria-hidden="true"
            className="connector-draw pointer-events-none absolute left-[3px] w-[3px] rounded-full bg-accent"
            style={{ top: bracket.top, height: bracket.height }}
          >
            {bracket.ticks.map((t, i) => (
              <span
                key={i}
                className="absolute -left-[3px] h-[3px] w-[9px] rounded-full bg-accent"
                style={{ top: t }}
              />
            ))}
          </div>
        )}

        {clusters.map((cl) => {
          const matched = activeEntity != null && matchedClusterKeys.has(cl.key);
          const dimmed = activeEntity != null && !matched;
          const isOpen = open.has(cl.key);
          return (
            <li
              key={cl.key}
              ref={(el) => {
                if (el) nodeRefs.current.set(cl.key, el);
                else nodeRefs.current.delete(cl.key);
              }}
              className={cn("relative pl-7 transition-opacity duration-2", dimmed && "opacity-30")}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-[4px] top-2 h-[13px] w-[13px] rotate-45 border-2 border-surface transition-colors",
                  matched ? "bg-accent" : "bg-border-strong",
                )}
              />
              <ClusterNode
                cluster={cl}
                open={isOpen}
                onToggle={() => toggle(cl.key)}
                activeEntity={activeEntity}
                matched={matched}
                onEntity={clickEntity}
              />
            </li>
          );
        })}
      </ol>

      <aside className="shrink-0 lg:w-56">
        <p className="mb-2 text-xs font-medium text-ink-tertiary">
          Entities
        </p>
        <ul className="space-y-0.5">
          {[...entityIndex.values()]
            .sort((a, b) => b.count - a.count)
            .map(({ ref, count }) => {
              const k = entityKey(ref);
              return (
                <li key={k}>
                  <button
                    type="button"
                    onClick={() => clickEntity(k)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1 text-left text-xs transition-colors hover:bg-surface-hover",
                      activeEntity === k ? "bg-surface-hover text-ink" : "text-ink-secondary",
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span
                        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", ENTITY_DOT[ref.kind])}
                      />
                      <span className="truncate">
                        <span className="text-ink-tertiary">{entityTypeLabel(ref.kind)} </span>
                        <span className="font-mono">{ref.label}</span>
                      </span>
                    </span>
                    <span className="shrink-0 font-mono tabular-nums text-ink-tertiary">{count}</span>
                  </button>
                </li>
              );
            })}
        </ul>
        {activeEntity && (
          <button
            type="button"
            onClick={() => setActiveEntity(null)}
            className="mt-2 px-2 text-xs font-medium text-ink-tertiary hover:text-ink"
          >
            Clear highlight
          </button>
        )}
      </aside>
    </div>
  );
}

function ClusterNode({
  cluster,
  open,
  onToggle,
  activeEntity,
  matched,
  onEntity,
}: {
  cluster: TimelineCluster;
  open: boolean;
  onToggle: () => void;
  activeEntity: string | null;
  matched: boolean;
  onEntity: (k: string) => void;
}) {
  const head = cluster.entries[0];
  const many = cluster.entries.length > 1;
  const entities = many
    ? dedupe(cluster.entries.flatMap(entitiesOf))
    : entitiesOf(head);

  return (
    <div
      className={cn(
        "rounded-md border bg-surface p-2.5 transition-colors",
        matched ? "border-accent-border" : "border-border",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-baseline justify-between gap-2 text-left"
      >
        <span className="font-mono text-xs font-medium text-ink">
          {many ? `${cluster.entries.length} × ${cluster.action}` : cluster.action}
        </span>
        <span className="shrink-0 text-2xs text-ink-tertiary">{relativeTime(head.created_at)}</span>
      </button>
      <div className="mt-0.5 text-2xs text-ink-tertiary">
        {actorOf(head)}
        {head.actor_role && head.actor_id ? ` · ${head.actor_id}` : ""}
      </div>

      {entities.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {entities.map((ref) => {
            const k = entityKey(ref);
            return (
              <button key={k} type="button" onClick={() => onEntity(k)}>
                <Badge tone={ENTITY_TONE[ref.kind]} variant={activeEntity === k ? "soft" : "outline"}>
                  {entityTypeLabel(ref.kind)} <span className="ml-1 font-mono">{ref.label}</span>
                </Badge>
              </button>
            );
          })}
        </div>
      )}

      {open && (
        <div className="mt-2 space-y-2 border-t border-border-subtle pt-2">
          {head.reason && <p className="text-xs text-ink-secondary">{head.reason}</p>}
          {cluster.entries.map((e) => (
            <div key={e.seq}>
              {many && (
                <p className="mb-0.5 font-mono text-2xs text-ink-tertiary">seq {e.seq}</p>
              )}
              <RecordDiff before={e.before} after={e.after} emptyLabel="No field changes." />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function dedupe(refs: EntityRef[]): EntityRef[] {
  const seen = new Set<string>();
  const out: EntityRef[] = [];
  for (const r of refs) {
    const k = entityKey(r);
    if (!seen.has(k)) {
      seen.add(k);
      out.push(r);
    }
  }
  return out;
}
