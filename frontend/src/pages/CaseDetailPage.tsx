import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignCase, getCase } from "../api/cases";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { RoleGate } from "../components/RoleGate";
import { StatusBadge } from "../components/StatusBadge";
import { AlertCard } from "../components/AlertCard";
import { Timeline } from "../components/Timeline";
import { NotesThread } from "../components/NotesThread";
import { AuditTable } from "../components/AuditTable";
import { TransitionControls } from "../components/TransitionControls";
import { relativeTime } from "../lib/format";

type Tab = "alerts" | "timeline" | "notes" | "audit";
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
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}

function AssignControl({ caseId, current }: { caseId: string; current: string | null }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [value, setValue] = useState(current ?? "");
  const mut = useMutation({
    mutationFn: (assigneeId: string | null) => assignCase(caseId, assigneeId, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", caseId] }),
  });
  const btn =
    "inline-flex min-h-control items-center rounded-md border border-border bg-surface px-3 text-sm font-medium text-ink-secondary shadow-xs transition-colors hover:border-border-strong hover:text-ink disabled:opacity-40";
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <input
        aria-label="Assignee id"
        name="assignee_id"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Assignee user ID, e.g. usr_a1b2c3…"
        className="min-h-control rounded-md border border-border bg-surface px-2.5 font-mono text-sm text-ink shadow-xs transition-colors placeholder:font-sans placeholder:text-ink-muted hover:border-border-strong focus-visible:border-accent"
      />
      <button
        type="button"
        className={btn}
        disabled={mut.isPending}
        onClick={() => mut.mutate(value || null)}
      >
        Assign
      </button>
      <button
        type="button"
        className={btn}
        disabled={mut.isPending}
        onClick={() => {
          setValue("");
          mut.mutate(null);
        }}
      >
        Unassign
      </button>
      {mut.isError && (
        <span role="alert" className="text-ink-danger">
          {mut.error instanceof ApiError ? (mut.error.detail ?? mut.error.message) : "Assign failed"}
        </span>
      )}
    </div>
  );
}

export function CaseDetailPage() {
  const { id = "" } = useParams();
  const { token } = useAuth();
  const [tab, setTab] = useState<Tab>("alerts");

  const query = useQuery({
    queryKey: ["case", id],
    queryFn: () => getCase(id, token),
    retry: false,
  });

  if (query.isLoading)
    return (
      <p className="text-sm text-ink-tertiary" aria-live="polite">
        Loading case…
      </p>
    );
  if (query.isError || !query.data) {
    return (
      <p
        role="alert"
        className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger-subtle-fg"
      >
        {query.error instanceof ApiError
          ? (query.error.detail ?? query.error.message)
          : "Case not found"}
      </p>
    );
  }

  const c = query.data;
  const assignee = c.assignee_email ?? c.assignee_id ?? "Unassigned";
  const tabs: Tab[] = ["alerts", "timeline", "notes", "audit"];

  return (
    <div className="u-enter space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-ink">{c.human_ref}</h1>
          <StatusBadge status={c.status} />
          {c.disposition && (
            <span className="rounded-full bg-surface-sunken px-2.5 py-0.5 text-xs text-ink-secondary">
              {c.disposition}
            </span>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border border-border bg-surface p-4 shadow-xs sm:grid-cols-3 lg:grid-cols-5">
          <Stat label="Assignee" value={assignee} />
          <Stat
            label="Risk"
            value={<span className="font-mono tabular-nums">{c.risk_score}</span>}
          />
          <Stat
            label="Alerts"
            value={<span className="font-mono tabular-nums">{c.alert_count}</span>}
          />
          <Stat label="Age" value={relativeTime(c.created_at)} />
          {c.version != null && (
            <Stat label="Version" value={<span className="font-mono">v{c.version}</span>} />
          )}
        </dl>
      </header>

      <RoleGate allow={["analyst", "admin"]}>
        <section className="space-y-3 rounded-lg border border-border bg-surface-raised p-4 shadow-sm">
          <TransitionControls caseId={c.id} status={c.status} version={c.version} />
          <div className="border-t border-border-subtle pt-3">
            <AssignControl caseId={c.id} current={c.assignee_id ?? null} />
          </div>
        </section>
      </RoleGate>

      <div>
        <nav className="flex gap-1 border-b border-border" aria-label="Case detail sections">
          {tabs.map((t) => {
            const active = tab === t;
            return (
              <button
                key={t}
                type="button"
                aria-current={active ? "page" : undefined}
                onClick={() => setTab(t)}
                className={`relative min-h-control px-3 text-sm font-medium transition-colors duration-2 ${
                  active ? "text-accent" : "text-ink-tertiary hover:text-ink"
                }`}
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

        <div className="u-enter pt-5">
          {tab === "alerts" && (
            <div className="u-stagger space-y-3">
              {c.alerts.map((a) => (
                <AlertCard key={a.id} alert={a} />
              ))}
              {c.alerts.length === 0 && (
                <p className="text-sm text-ink-tertiary">No alerts in this case.</p>
              )}
            </div>
          )}
          {tab === "timeline" && <Timeline entries={c.timeline} />}
          {tab === "notes" && <NotesThread caseId={c.id} notes={c.notes} />}
          {tab === "audit" && <AuditTable caseId={c.id} entries={c.timeline} />}
        </div>
      </div>
    </div>
  );
}
