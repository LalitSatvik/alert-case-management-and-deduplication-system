export type Role = "analyst" | "admin" | "readonly";
export type GroupingMethod = "deterministic" | "similarity" | "singleton" | "manual";
export type Direction = "inbound" | "outbound" | "internal";

export interface GroupingInfo {
  method: GroupingMethod;
  matched_rule_ids: string[];
  similarity_score: number | null;
  feature_contributions: Record<string, number>;
  engine_version: string;
  config_hash: string;
}

export interface AlertOut {
  id: string;
  received_at?: string;
  case_id?: string | null;
  grouping: GroupingInfo | null;
  external_alert_id: string;
  source_system?: string;
  event_time?: string;
  amount: string;
  currency: string;
  direction?: Direction;
  customer_ref?: string | null;
  account_ref?: string | null;
  counterparty_ref?: string | null;
  merchant_name?: string | null;
  mcc?: string | null;
  device_id?: string | null;
  ip_address?: string | null;
  session_id?: string | null;
  risk_score?: number | null;
  rule_codes?: string[];
  typologies?: string[];
  raw_payload?: Record<string, unknown>;
  ground_truth_group_id?: string | null;
}

export interface NoteOut {
  id: string;
  case_id: string;
  author_id: string;
  body: string;
  retracted: boolean;
  retraction_reason: string | null;
  created_at: string;
}

export interface TimelineEntry {
  seq: number;
  action: string;
  // Backend `TimelineEntry` carries `actor_id` + `actor_role` only — there is
  // no resolved actor name (no `/users` endpoint in v1).
  actor_id?: string | null;
  actor_role?: string | null;
  reason?: string | null;
  created_at: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface CaseListItem {
  id: string;
  human_ref: string;
  status: string;
  disposition?: string | null;
  assignee_email: string | null;
  risk_score: number;
  alert_count: number;
  created_at: string;
  updated_at?: string;
  oldest_alert_event_time?: string | null;
}

export interface CaseOut {
  id: string;
  human_ref: string;
  status: string;
  disposition: string | null;
  assignee_id?: string | null;
  assignee_email?: string | null;
  risk_score: number;
  alert_count: number;
  closed_at?: string | null;
  canonical_from_case_id?: string | null;
  version?: number;
  created_at: string;
  updated_at?: string;
}

export interface CaseDetail extends CaseOut {
  alerts: AlertOut[];
  notes: NoteOut[];
  timeline: TimelineEntry[];
}

export interface CaseListResponse {
  items: CaseListItem[];
  next_cursor: string | null;
}
