import type { CSSProperties } from "react";
import type { GroupingInfo } from "../api/types";

const chip =
  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset";

export function GroupingRationale({ grouping }: { grouping: GroupingInfo | null }) {
  if (!grouping) {
    return (
      <span className={`${chip} bg-neutral-subtle text-neutral-subtle-fg ring-neutral-border`}>
        ungrouped
      </span>
    );
  }

  if (grouping.method === "deterministic") {
    const rules = grouping.matched_rule_ids.join(", ") || "no rules";
    return (
      <span className={`${chip} bg-success-subtle text-success-subtle-fg ring-success-border`}>
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-success"
        />
        {`Deterministic · `}
        <span className="font-mono">{rules}</span>
      </span>
    );
  }

  if (grouping.method === "similarity") {
    const score = (grouping.similarity_score ?? 0).toFixed(2);
    const entries = Object.entries(grouping.feature_contributions);
    return (
      <div className="text-xs">
        <span className={`${chip} bg-info-subtle text-info-subtle-fg ring-info-border`}>
          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-info" />
          {`Similarity `}
          <span className="font-mono tabular-nums">{score}</span>
        </span>
        <dl className="mt-2 space-y-1">
          {entries.map(([k, v], i) => {
            const pct = Math.max(0, Math.min(1, v));
            return (
              <div key={k} className="flex items-center gap-2">
                <dt className="w-20 shrink-0 truncate font-mono text-ink-tertiary">{k}</dt>
                <dd className="flex flex-1 items-center gap-2">
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--scorebar-track)]">
                    <span
                      className="score-fill block h-full rounded-full bg-[var(--scorebar-fill)]"
                      style={
                        {
                          "--score": pct,
                          transitionDelay: `${i * 45}ms`,
                        } as CSSProperties
                      }
                    />
                  </span>
                  <span className="w-9 shrink-0 text-right font-mono tabular-nums text-ink-tertiary">
                    {v.toFixed(2)}
                  </span>
                </dd>
              </div>
            );
          })}
        </dl>
      </div>
    );
  }

  return (
    <span className={`${chip} bg-neutral-subtle text-neutral-subtle-fg ring-neutral-border`}>
      no group
    </span>
  );
}
