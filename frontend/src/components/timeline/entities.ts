import type { TimelineEntry } from "../../api/types";

export type EntityKind = "alert" | "note" | "user" | "method" | "status";

export interface EntityRef {
  kind: EntityKind;
  id: string;
  label: string;
}

const KIND_LABEL: Record<EntityKind, string> = {
  alert: "Alert",
  note: "Note",
  user: "User",
  method: "Method",
  status: "Status",
};

export function entityKey(e: EntityRef): string {
  return `${e.kind}:${e.id}`;
}

export function entityTypeLabel(kind: EntityKind): string {
  return KIND_LABEL[kind];
}

function shortId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

function pushUnique(list: EntityRef[], ref: EntityRef) {
  const k = entityKey(ref);
  if (!list.some((e) => entityKey(e) === k)) list.push(ref);
}

/** Entities an event touches — parsed from its action, actor, and before/after JSON. */
export function entitiesOf(entry: TimelineEntry): EntityRef[] {
  const out: EntityRef[] = [];
  const bag = { ...(entry.before ?? {}), ...(entry.after ?? {}) } as Record<string, unknown>;

  if (entry.actor_id) {
    pushUnique(out, { kind: "user", id: entry.actor_id, label: shortId(entry.actor_id) });
  }

  const alertId = bag.alert_id;
  if (typeof alertId === "string") {
    pushUnique(out, { kind: "alert", id: alertId, label: shortId(alertId) });
  }
  const noteId = bag.note_id;
  if (typeof noteId === "string") {
    pushUnique(out, { kind: "note", id: noteId, label: shortId(noteId) });
  }
  const assignee = bag.assignee_id;
  if (typeof assignee === "string") {
    pushUnique(out, { kind: "user", id: assignee, label: shortId(assignee) });
  }
  const method = bag.method;
  if (typeof method === "string") {
    pushUnique(out, { kind: "method", id: method, label: method });
  }
  for (const key of ["status"] as const) {
    for (const src of [entry.before, entry.after]) {
      const v = src?.[key];
      if (typeof v === "string") pushUnique(out, { kind: "status", id: v, label: v });
    }
  }

  return out;
}

const SECOND = /\.\d+/;

/** A run of same-action events in the same second collapses into one cluster. */
export interface TimelineCluster {
  key: string;
  action: string;
  entries: TimelineEntry[];
}

export function clusterEntries(entries: TimelineEntry[]): TimelineCluster[] {
  const clusters: TimelineCluster[] = [];
  for (const entry of entries) {
    const bucket = entry.created_at.replace(SECOND, "");
    const last = clusters[clusters.length - 1];
    if (
      last &&
      last.action === entry.action &&
      last.entries[0].created_at.replace(SECOND, "") === bucket &&
      entry.action === "case.alert_linked"
    ) {
      last.entries.push(entry);
    } else {
      clusters.push({ key: `${entry.seq}`, action: entry.action, entries: [entry] });
    }
  }
  return clusters;
}
