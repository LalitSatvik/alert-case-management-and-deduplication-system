import { apiFetch } from "./client";
import type { CaseDetail, CaseListResponse, CaseOut, CaseStats, NoteOut } from "./types";

export interface CaseQuery {
  status?: string[];
  disposition?: string[];
  assignee_id?: string;
  risk_min?: number;
  risk_max?: number;
  source_system?: string;
  typology?: string;
  q?: string;
  sort?: string;
  cursor?: string;
  limit?: number;
}

function toQueryString(params: CaseQuery): string {
  const sp = new URLSearchParams();
  params.status?.forEach((s) => sp.append("status", s));
  params.disposition?.forEach((d) => sp.append("disposition", d));
  if (params.assignee_id) sp.set("assignee_id", params.assignee_id);
  if (params.risk_min != null) sp.set("risk_min", String(params.risk_min));
  if (params.risk_max != null) sp.set("risk_max", String(params.risk_max));
  if (params.source_system) sp.set("source_system", params.source_system);
  if (params.typology) sp.set("typology", params.typology);
  if (params.q) sp.set("q", params.q);
  if (params.sort) sp.set("sort", params.sort);
  if (params.cursor) sp.set("cursor", params.cursor);
  if (params.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export function listCases(params: CaseQuery, token: string | null): Promise<CaseListResponse> {
  return apiFetch<CaseListResponse>(`/cases${toQueryString(params)}`, { token });
}

/** Aggregate counts for the case list. Pass the same `CaseQuery` as `listCases`
 *  (sort / cursor / limit are ignored server-side) so the strip matches the table. */
export function getCaseStats(params: CaseQuery, token: string | null): Promise<CaseStats> {
  return apiFetch<CaseStats>(`/cases/stats${toQueryString(params)}`, { token });
}

export function getCase(id: string, token: string | null): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/cases/${id}`, { token });
}

export interface TransitionBody {
  to: string;
  reason?: string;
  disposition?: string;
}

export function transitionCase(
  id: string,
  body: TransitionBody,
  token: string | null,
  ifMatch?: number,
): Promise<CaseOut> {
  return apiFetch<CaseOut>(`/cases/${id}/transition`, {
    method: "POST",
    body,
    token,
    headers: ifMatch != null ? { "If-Match": String(ifMatch) } : undefined,
  });
}

export function assignCase(
  id: string,
  assignee_id: string | null,
  token: string | null,
): Promise<CaseOut> {
  return apiFetch<CaseOut>(`/cases/${id}/assign`, {
    method: "POST",
    body: { assignee_id },
    token,
  });
}

export function addNote(id: string, body: string, token: string | null): Promise<NoteOut> {
  return apiFetch<NoteOut>(`/cases/${id}/notes`, { method: "POST", body: { body }, token });
}

export function retractNote(
  caseId: string,
  noteId: string,
  reason: string,
  token: string | null,
): Promise<NoteOut> {
  return apiFetch<NoteOut>(`/cases/${caseId}/notes/${noteId}/retract`, {
    method: "POST",
    body: { reason },
    token,
  });
}

/** The audit export bundle returned by `format=json`. */
export interface AuditExportBundle {
  chain_verified: boolean;
  [key: string]: unknown;
}

export function exportAudit(id: string, format: "json", token: string | null): Promise<AuditExportBundle>;
export function exportAudit(id: string, format: "html", token: string | null): Promise<string>;
export function exportAudit(
  id: string,
  format: "json" | "html",
  token: string | null,
): Promise<AuditExportBundle | string> {
  return apiFetch<AuditExportBundle | string>(`/cases/${id}/audit:export?format=${format}`, {
    method: "POST",
    body: {},
    token,
    // The backend returns `text/html` for the HTML export; take it verbatim
    // instead of letting `apiFetch` try to `JSON.parse` it.
    raw: format === "html",
  });
}
