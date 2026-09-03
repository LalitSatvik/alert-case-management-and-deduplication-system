import { CASE_STATUSES } from "./caseFilters";
import type { UserOut } from "../api/types";

const KEY = "acms.savedViews";

export interface SavedView {
  id: string;
  name: string;
  /** The query string (without leading "?") this view applies. */
  query: string;
}

export function listSavedViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    return [];
  }
}

function persist(views: SavedView[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(views));
  } catch {
    /* storage unavailable — saved views just won't persist */
  }
}

export function saveView(name: string, query: string): SavedView {
  const view: SavedView = { id: crypto.randomUUID(), name: name.trim(), query };
  persist([...listSavedViews().filter((v) => v.name !== view.name), view]);
  return view;
}

export function deleteView(id: string) {
  persist(listSavedViews().filter((v) => v.id !== id));
}

/**
 * Drop filters a saved view references that no longer resolve — an assignee that
 * left, a status that was removed — and keep the rest, so one stale value never
 * breaks the whole view. Returns the cleaned query string.
 */
export function sanitizeViewQuery(query: string, users: UserOut[]): string {
  const sp = new URLSearchParams(query);
  const known = new Set<string>(CASE_STATUSES);

  const statuses = sp.getAll("status").filter((s) => known.has(s));
  sp.delete("status");
  statuses.forEach((s) => sp.append("status", s));

  const assignee = sp.get("assignee");
  if (
    assignee &&
    !["all", "me", "unassigned"].includes(assignee) &&
    !users.some((u) => u.id === assignee)
  ) {
    sp.delete("assignee");
  }

  return sp.toString();
}
