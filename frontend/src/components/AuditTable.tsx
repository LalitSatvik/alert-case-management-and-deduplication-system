import { useState } from "react";
import type { TimelineEntry } from "../api/types";
import { exportAudit } from "../api/cases";
import { useAuth } from "../auth/AuthContext";
import { downloadHtml, downloadJson, relativeTime } from "../lib/format";
import { Badge, type BadgeTone } from "./ui/Badge";
import { Button } from "./ui/Button";

const CHAIN: Record<"unknown" | "verified" | "broken", { text: string; tone: BadgeTone }> = {
  unknown: { text: "Chain not checked", tone: "neutral" },
  verified: { text: "Chain verified", tone: "success" },
  broken: { text: "Chain broken", tone: "danger" },
};

export function AuditTable({ caseId, entries }: { caseId: string; entries: TimelineEntry[] }) {
  const { token } = useAuth();
  const [busy, setBusy] = useState<null | "json" | "html">(null);
  const [error, setError] = useState<string | null>(null);
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

  const pill = CHAIN[chain];
  const sorted = [...(entries ?? [])].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
  const th =
    "sticky top-0 z-10 border-b border-border bg-surface px-cell-x py-cell-y text-left text-xs font-medium text-ink-tertiary";
  const td = "border-b border-border-subtle px-cell-x py-cell-y align-top";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={pill.tone} dot>
          {pill.text}
        </Badge>
        <div className="ml-auto flex gap-1">
          <Button size="sm" disabled={busy !== null} onClick={() => onExport("json")}>
            Export JSON
          </Button>
          <Button size="sm" disabled={busy !== null} onClick={() => onExport("html")}>
            Export HTML
          </Button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-ink-danger">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-xs">
        <table className="min-w-full border-separate border-spacing-0 text-table">
          <thead>
            <tr>
              <th className={`${th} w-12`}>Seq</th>
              <th className={`${th} w-24`}>Time</th>
              <th className={`${th} w-28`}>Actor</th>
              <th className={th}>Action</th>
              <th className={th}>Change</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.seq} className="transition-colors hover:bg-surface-hover">
                <td className={`${td} font-mono tabular-nums text-ink-tertiary`}>{e.seq}</td>
                <td className={`${td} text-ink-secondary`}>{relativeTime(e.created_at)}</td>
                <td className={`${td} font-mono text-2xs text-ink-secondary`}>
                  {e.actor_role ?? e.actor_id ?? "system"}
                </td>
                <td className={`${td} font-mono font-medium text-ink`}>{e.action}</td>
                <td className={`${td} font-mono text-2xs text-ink-tertiary`}>
                  {e.before || e.after
                    ? `${JSON.stringify(e.before ?? {})} → ${JSON.stringify(e.after ?? {})}`
                    : "—"}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={5} className="px-cell-x py-10 text-center text-sm text-ink-tertiary">
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
