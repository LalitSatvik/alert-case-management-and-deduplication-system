import type { CSSProperties } from "react";
import type { GroupingInfo } from "../../api/types";
import { Badge, type BadgeTone } from "../ui/Badge";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/Popover";

const LABEL: Record<string, { text: string; tone: BadgeTone }> = {
  deterministic: { text: "Deterministic", tone: "success" },
  similarity: { text: "Similarity", tone: "info" },
  singleton: { text: "Singleton", tone: "neutral" },
  manual: { text: "Manual", tone: "warning" },
};

export function GroupingBadge({ grouping }: { grouping: GroupingInfo | null }) {
  if (!grouping) {
    return (
      <Badge tone="neutral" variant="outline" uppercase>
        No group
      </Badge>
    );
  }

  const meta = LABEL[grouping.method] ?? { text: grouping.method, tone: "neutral" as BadgeTone };

  if (grouping.method === "deterministic") {
    return (
      <Popover>
        <PopoverTrigger>
          <Badge tone={meta.tone} dot uppercase>
            {meta.text}
          </Badge>
        </PopoverTrigger>
        <PopoverContent className="w-72">
          <p className="mb-1 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
            Matched rules
          </p>
          <ul className="space-y-0.5 font-mono text-xs text-ink-secondary">
            {grouping.matched_rule_ids.length ? (
              grouping.matched_rule_ids.map((r) => <li key={r}>{r}</li>)
            ) : (
              <li className="text-ink-tertiary">none</li>
            )}
          </ul>
          <p className="mt-2 font-mono text-2xs text-ink-tertiary">
            engine {grouping.engine_version}
          </p>
        </PopoverContent>
      </Popover>
    );
  }

  if (grouping.method === "similarity") {
    const score = (grouping.similarity_score ?? 0).toFixed(2);
    const entries = Object.entries(grouping.feature_contributions);
    return (
      <Popover>
        <PopoverTrigger>
          <Badge tone={meta.tone} dot uppercase>
            {meta.text} <span className="ml-1 font-mono tabular-nums">{score}</span>
          </Badge>
        </PopoverTrigger>
        <PopoverContent className="w-72">
          <p className="mb-2 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
            Feature contributions
          </p>
          <dl className="space-y-1">
            {entries.map(([k, v], i) => {
              const pct = Math.max(0, Math.min(1, v));
              return (
                <div key={k} className="flex items-center gap-2 text-xs">
                  <dt className="w-16 shrink-0 truncate font-mono text-ink-tertiary">{k}</dt>
                  <dd className="flex flex-1 items-center gap-2">
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--scorebar-track)]">
                      <span
                        className="score-fill block h-full rounded-full bg-[var(--scorebar-fill)]"
                        style={{ "--score": pct, transitionDelay: `${i * 40}ms` } as CSSProperties}
                      />
                    </span>
                    <span className="w-8 shrink-0 text-right font-mono tabular-nums text-ink-tertiary">
                      {v.toFixed(2)}
                    </span>
                  </dd>
                </div>
              );
            })}
          </dl>
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Badge tone={meta.tone} variant="outline" uppercase>
      {meta.text}
    </Badge>
  );
}
