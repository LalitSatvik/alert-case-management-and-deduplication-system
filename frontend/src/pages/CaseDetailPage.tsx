import type { ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCase } from "../api/cases";
import { listUsers } from "../api/users";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { AlertsTable } from "../components/alerts/AlertsTable";
import { Timeline } from "../components/Timeline";
import { NotesThread } from "../components/NotesThread";
import { AuditTable } from "../components/AuditTable";
import { ActionToolbar } from "../components/case/ActionToolbar";
import { StatusHistory } from "../components/case/StatusHistory";
import { Page, PageBody, PageHeader } from "../components/ui/Page";
import { RiskScore } from "../components/ui/RiskScore";
import { cn } from "../components/ui/cn";
import { relativeTime } from "../lib/format";

const TABS = ["alerts", "timeline", "notes", "audit"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL: Record<Tab, string> = {
  alerts: "Alerts",
  timeline: "Timeline",
  notes: "Notes",
  audit: "Audit",
};

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">{label}</dt>
      <dd className="text-xs text-ink">{value}</dd>
    </div>
  );
}

export function CaseDetailPage() {
  const { id = "" } = useParams();
  const { token } = useAuth();
  const [sp, setSp] = useSearchParams();
  const tab: Tab = (TABS as readonly string[]).includes(sp.get("tab") ?? "")
    ? (sp.get("tab") as Tab)
    : "alerts";

  const query = useQuery({ queryKey: ["case", id], queryFn: () => getCase(id, token), retry: false });
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => listUsers(token),
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <Page>
        <PageBody>
          <p className="text-sm text-ink-tertiary" aria-live="polite">
            Loading case…
          </p>
        </PageBody>
      </Page>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Page>
        <PageBody>
          <p
            role="alert"
            className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger-subtle-fg"
          >
            {query.error instanceof ApiError
              ? (query.error.detail ?? query.error.message)
              : "Case not found"}
          </p>
        </PageBody>
      </Page>
    );
  }

  const c = query.data;
  const users = Array.isArray(usersQuery.data) ? usersQuery.data : [];

  const setTab = (t: Tab) =>
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev);
        n.set("tab", t);
        return n;
      },
      { replace: true },
    );

  return (
    <Page>
      <PageHeader title={<span className="font-mono tracking-tight">{c.human_ref}</span>}>
        <StatusBadge status={c.status} />
        {c.disposition && (
          <span className="rounded-sm bg-surface-sunken px-2 py-0.5 text-2xs font-medium uppercase tracking-wide text-ink-secondary">
            {c.disposition}
          </span>
        )}
      </PageHeader>

      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[19rem] shrink-0 flex-col gap-4 overflow-y-auto border-r border-border p-4">
          <div className="flex items-center justify-between">
            <RiskScore score={c.risk_score} size="md" />
            {c.version != null && (
              <span className="font-mono text-2xs text-ink-tertiary">v{c.version}</span>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <Stat
              label="Assignee"
              value={c.assignee_email ?? (c.assignee_id ? "Assigned" : "Unassigned")}
            />
            <Stat
              label="Alerts"
              value={<span className="font-mono tabular-nums">{c.alert_count}</span>}
            />
            <Stat label="Age" value={relativeTime(c.created_at)} />
            {c.closed_at && <Stat label="Closed" value={relativeTime(c.closed_at)} />}
          </dl>

          <div className="border-t border-border-subtle pt-3">
            <ActionToolbar
              caseId={c.id}
              status={c.status}
              version={c.version}
              assigneeId={c.assignee_id ?? null}
              assigneeEmail={c.assignee_email ?? null}
              users={users}
            />
          </div>

          <div className="border-t border-border-subtle pt-3">
            <StatusHistory timeline={c.timeline} />
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <nav
            className="flex shrink-0 gap-1 border-b border-border px-4"
            aria-label="Case detail sections"
          >
            {TABS.map((t) => {
              const active = tab === t;
              return (
                <button
                  key={t}
                  type="button"
                  aria-current={active ? "page" : undefined}
                  onClick={() => setTab(t)}
                  className={cn(
                    "relative min-h-control px-3 text-sm font-medium transition-colors duration-2",
                    active ? "text-accent" : "text-ink-tertiary hover:text-ink",
                  )}
                >
                  {TAB_LABEL[t]}
                  {active && (
                    <span
                      aria-hidden="true"
                      className="tab-underline absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-[var(--tab-indicator)]"
                    />
                  )}
                </button>
              );
            })}
          </nav>

          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {tab === "alerts" && <AlertsTable alerts={c.alerts} />}
            {tab === "timeline" && <Timeline entries={c.timeline} />}
            {tab === "notes" && <NotesThread caseId={c.id} notes={c.notes} />}
            {tab === "audit" && <AuditTable caseId={c.id} entries={c.timeline} />}
          </div>
        </div>
      </div>
    </Page>
  );
}
