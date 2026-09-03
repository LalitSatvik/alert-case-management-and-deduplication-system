import { useState } from "react";
import type { TimelineEntry } from "../api/types";
import { exportAudit } from "../api/cases";
import { useAuth } from "../auth/AuthContext";
import { downloadHtml, downloadJson, relativeTime } from "../lib/format";

export function AuditTable({
  caseId,
  entries,
}: {
  caseId: string;
  entries: TimelineEntry[];
}) {
  const { token } = useAuth();
  const [busy, setBusy] = useState<null | "json" | "html">(null);
  const [error, setError] = useState<string | null>(null);
  // The hash chain is only known to be intact once a JSON export has been run
  // and its `chain_verified` flag read back — never assume it before then.
  const [chain, setChain] = useState<"unknown" | "verified" | "broken">("unknown");

  async function onExport(format: "json" | "html") {
    setBusy(format);
    setError(null);
    try {
      if (format === "json") {
        const bundle = await exportAudit(caseId, "json", token);
        downloadJson(`case-${caseId}-audit.json`, bundle);
        setChain(bundle.chain_verified ? "verified" : "broken");
      } else {
        const html = await exportAudit(caseId, "html", token);
        downloadHtml(`case-${caseId}-audit.html`, html);
      }
    } catch {
      setError("Export failed");
    } finally {
      setBusy(null);
    }
  }

  const chainPill = {
    unknown: {
      text: "Chain not checked",
      cls: "bg-neutral-subtle text-neutral-subtle-fg ring-neutral-border",
      dot: "bg-ink-muted",
    },
    verified: {
      text: "Chain verified",
      cls: "bg-success-subtle text-success-subtle-fg ring-success-border",
      dot: "bg-success",
    },
    broken: {
      text: "Chain broken",
      cls: "bg-danger-subtle text-danger-subtle-fg ring-danger-border",
      dot: "bg-danger",
    },
  }[chain];

  const sorted = [...(entries ?? [])].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset transition-colors duration-3 ${chainPill.cls}`}
        >
          <span
            aria-hidden="true"
            className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-3 ${chainPill.dot}`}
          />
          {chainPill.text}
        </span>
        <div className="ml-auto inline-flex overflow-hidden rounded-md border border-border shadow-xs">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => onExport("json")}
            className="min-h-control bg-surface px-3.5 text-sm font-medium text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink disabled:opacity-40"
          >
            Export JSON
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => onExport("html")}
            className="min-h-control border-l border-border bg-surface px-3.5 text-sm font-medium text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink disabled:opacity-40"
          >
            Export HTML
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-ink-danger">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-xs">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left text-2xs uppercase tracking-wider text-ink-tertiary">
              <th className="border-b border-border bg-surface-sunken px-3.5 py-2.5 font-semibold">Seq</th>
              <th className="border-b border-border bg-surface-sunken px-3.5 py-2.5 font-semibold">Time</th>
              <th className="border-b border-border bg-surface-sunken px-3.5 py-2.5 font-semibold">Actor</th>
              <th className="border-b border-border bg-surface-sunken px-3.5 py-2.5 font-semibold">Action</th>
              <th className="border-b border-border bg-surface-sunken px-3.5 py-2.5 font-semibold">Change</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.seq} className="transition-colors hover:bg-surface-hover">
                <td className="border-b border-border-subtle px-3.5 py-2.5 font-mono text-ink-tertiary">
                  {e.seq}
                </td>
                <td className="border-b border-border-subtle px-3.5 py-2.5 text-ink-secondary">
                  {relativeTime(e.created_at)}
                </td>
                <td className="border-b border-border-subtle px-3.5 py-2.5 text-ink-secondary">
                  {e.actor_role ?? e.actor_id ?? "system"}
                </td>
                <td className="border-b border-border-subtle px-3.5 py-2.5 font-mono font-medium text-ink">
                  {e.action}
                </td>
                <td className="border-b border-border-subtle px-3.5 py-2.5 font-mono text-xs text-ink-tertiary">
                  {e.before || e.after
                    ? `${JSON.stringify(e.before ?? {})} → ${JSON.stringify(e.after ?? {})}`
                    : "—"}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3.5 py-10 text-center text-sm text-ink-tertiary">
                  No audit entries.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
