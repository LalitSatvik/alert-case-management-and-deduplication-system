import type { CaseQuery } from "../api/cases";

export const CASE_STATUSES = ["Open", "In Progress", "Pending Info", "Closed", "Merged"] as const;

// Close dispositions — mirrors backend config/grouping.yaml (also in lib/lifecycle).
export const DISPOSITIONS = [
  "No action",
  "Escalate",
  "Confirmed fraud",
  "Confirmed AML concern",
  "Duplicate",
] as const;

// Values the synthetic generator produces — what the UI actually sees.
export const TYPOLOGIES = [
  "structuring",
  "layering",
  "card-testing",
  "account-takeover",
  "mule-network",
] as const;

export const SOURCE_SYSTEMS = ["acme-fraud", "txmon-core", "sanctions-screen"] as const;

export const SORTS = [
  { value: "-risk_score", label: "Risk" },
  { value: "-created_at", label: "Newest" },
  { value: "oldest_alert", label: "Oldest alert" },
] as const;

export const DEFAULT_SORT = "-risk_score";

/** All filter state lives in the URL query string. This reads it into one place. */
export interface CaseFilterState {
  statuses: string[];
  assignee: string; // "all" | "me" | "unassigned" | <userId>
  riskMin: number | null;
  riskMax: number | null;
  dispositions: string[];
  sourceSystem: string;
  typology: string;
  createdFrom: string; // yyyy-mm-dd
  createdTo: string;
  q: string;
  sort: string;
}

export function readFilterState(sp: URLSearchParams): CaseFilterState {
  return {
    statuses: sp.getAll("status"),
    assignee: sp.get("assignee") ?? "all",
    riskMin: numOrNull(sp.get("risk_min")),
    riskMax: numOrNull(sp.get("risk_max")),
    dispositions: sp.getAll("disposition"),
    sourceSystem: sp.get("source_system") ?? "",
    typology: sp.get("typology") ?? "",
    createdFrom: sp.get("created_from") ?? "",
    createdTo: sp.get("created_to") ?? "",
    q: sp.get("q") ?? "",
    sort: sp.get("sort") ?? DEFAULT_SORT,
  };
}

/** Build the API query from URL state. `principalId` resolves the "me" assignee. */
export function toCaseQuery(state: CaseFilterState, principalId?: string): CaseQuery {
  const assignee_id =
    state.assignee === "unassigned"
      ? "unassigned"
      : state.assignee === "me"
        ? principalId
        : state.assignee !== "all"
          ? state.assignee
          : undefined;

  return {
    status: state.statuses.length ? state.statuses : undefined,
    disposition: state.dispositions.length ? state.dispositions : undefined,
    assignee_id,
    risk_min: state.riskMin ?? undefined,
    risk_max: state.riskMax ?? undefined,
    source_system: state.sourceSystem || undefined,
    typology: state.typology || undefined,
    created_from: state.createdFrom ? new Date(state.createdFrom).toISOString() : undefined,
    created_to: state.createdTo ? new Date(state.createdTo).toISOString() : undefined,
    q: state.q || undefined,
    sort: state.sort,
  };
}

/** How many non-default filters are active — drives the "Advanced (n)" badge. */
export function activeFilterCount(s: CaseFilterState): number {
  let n = 0;
  if (s.dispositions.length) n += 1;
  if (s.riskMin != null) n += 1;
  if (s.riskMax != null) n += 1;
  if (s.sourceSystem) n += 1;
  if (s.typology) n += 1;
  if (s.createdFrom) n += 1;
  if (s.createdTo) n += 1;
  return n;
}

function numOrNull(v: string | null): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
