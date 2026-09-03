import { useMemo, useState, type ReactNode } from "react";
import { cn } from "./cn";

type Val = unknown;

export interface DiffRow {
  key: string;
  status: "added" | "removed" | "changed" | "same";
  before: Val;
  after: Val;
}

function fmt(v: Val): string {
  if (v === undefined) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

export function diffRecords(
  before: Record<string, Val> | null | undefined,
  after: Record<string, Val> | null | undefined,
  { includeSame = false }: { includeSame?: boolean } = {},
): DiffRow[] {
  const a = before ?? {};
  const b = after ?? {};
  const keys = Array.from(new Set([...Object.keys(a), ...Object.keys(b)])).sort();
  const rows: DiffRow[] = [];
  for (const key of keys) {
    const inA = key in a;
    const inB = key in b;
    const same = JSON.stringify(a[key]) === JSON.stringify(b[key]);
    let status: DiffRow["status"];
    if (same) status = "same";
    else if (!inA) status = "added";
    else if (!inB) status = "removed";
    else status = "changed";
    if (status === "same" && !includeSame) continue;
    rows.push({ key, status, before: a[key], after: b[key] });
  }
  return rows;
}

/** Cheap word-level diff for two strings — marks removed / added spans. */
function wordDiff(before: string, after: string): { a: ReactNode; b: ReactNode } {
  const aw = before.split(/(\s+)/);
  const bw = after.split(/(\s+)/);
  const bSet = new Set(bw);
  const aSet = new Set(aw);
  return {
    a: aw.map((w, i) =>
      w.trim() && !bSet.has(w) ? (
        <mark key={i} className="rounded-sm bg-diff-del-bg px-0.5 text-diff-del-fg">
          {w}
        </mark>
      ) : (
        <span key={i}>{w}</span>
      ),
    ),
    b: bw.map((w, i) =>
      w.trim() && !aSet.has(w) ? (
        <mark key={i} className="rounded-sm bg-diff-add-bg px-0.5 text-diff-add-fg">
          {w}
        </mark>
      ) : (
        <span key={i}>{w}</span>
      ),
    ),
  };
}

const DOT: Record<DiffRow["status"], string> = {
  added: "text-diff-add-fg",
  removed: "text-diff-del-fg",
  changed: "text-warning-subtle-fg",
  same: "text-ink-tertiary",
};

export function RecordDiff({
  before,
  after,
  emptyLabel = "No differences.",
}: {
  before?: Record<string, Val> | null;
  after?: Record<string, Val> | null;
  emptyLabel?: string;
}) {
  const [mode, setMode] = useState<"unified" | "split">("unified");
  const rows = useMemo(() => diffRecords(before, after), [before, after]);

  if (rows.length === 0) return <p className="text-sm text-ink-tertiary">{emptyLabel}</p>;

  return (
    <div className="space-y-2">
      <div className="flex gap-1 rounded-md border border-border bg-surface-sunken p-0.5 text-2xs">
        {(["unified", "split"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={cn(
              "rounded-sm px-2 py-0.5 font-medium uppercase tracking-wide transition-colors",
              mode === m ? "bg-surface text-ink shadow-xs" : "text-ink-tertiary hover:text-ink",
            )}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        {mode === "unified" ? (
          <table className="w-full font-mono text-xs">
            <tbody>
              {rows.map((r) => {
                const wd = r.status === "changed" ? wordDiff(fmt(r.before), fmt(r.after)) : null;
                return (
                  <tr key={r.key} className="border-b border-border-subtle last:border-0">
                    <td className={cn("w-4 select-none px-2 py-1 text-center align-top", DOT[r.status])}>
                      {r.status === "added" ? "+" : r.status === "removed" ? "−" : "~"}
                    </td>
                    <td className="w-40 px-2 py-1 align-top text-ink-tertiary">{r.key}</td>
                    <td className="px-2 py-1 align-top">
                      {r.status === "removed" && (
                        <span className="text-diff-del-fg line-through">{fmt(r.before)}</span>
                      )}
                      {r.status === "added" && (
                        <span className="text-diff-add-fg">{fmt(r.after)}</span>
                      )}
                      {r.status === "changed" && (
                        <span className="flex flex-wrap gap-x-1">
                          <span className="text-diff-del-fg line-through">{wd!.a}</span>
                          <span className="text-ink-tertiary">→</span>
                          <span className="text-diff-add-fg">{wd!.b}</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <table className="w-full font-mono text-xs">
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-b border-border-subtle last:border-0">
                  <td className="w-36 px-2 py-1 align-top text-ink-tertiary">{r.key}</td>
                  <td
                    className={cn(
                      "w-1/2 px-2 py-1 align-top",
                      r.status !== "added" && "bg-diff-del-bg",
                    )}
                  >
                    <span className={r.status !== "added" ? "text-diff-del-fg" : "text-ink-tertiary"}>
                      {r.status === "added" ? "" : fmt(r.before)}
                    </span>
                  </td>
                  <td
                    className={cn(
                      "w-1/2 px-2 py-1 align-top",
                      r.status !== "removed" && "bg-diff-add-bg",
                    )}
                  >
                    <span className={r.status !== "removed" ? "text-diff-add-fg" : "text-ink-tertiary"}>
                      {r.status === "removed" ? "" : fmt(r.after)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
