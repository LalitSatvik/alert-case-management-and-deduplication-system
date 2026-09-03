import { useQuery } from "@tanstack/react-query";
import { getCaseStats, type CaseQuery } from "../../api/cases";
import { useAuth } from "../../auth/AuthContext";
import { cn } from "../ui/cn";

function Chip({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string | number;
  emphasis?: "danger" | "warn";
}) {
  return (
    <div className="flex items-baseline gap-1.5 whitespace-nowrap">
      <span
        className={cn(
          "font-mono text-sm font-semibold tabular-nums",
          emphasis === "danger" ? "text-risk-crit-fg" : emphasis === "warn" ? "text-risk-elev-fg" : "text-ink",
        )}
      >
        {value}
      </span>
      <span className="text-2xs font-medium uppercase tracking-wider text-ink-tertiary">{label}</span>
    </div>
  );
}

export function CasesSummary({ query }: { query: CaseQuery }) {
  const { token } = useAuth();
  // Same filter set as the list, minus paging — the strip describes the whole result.
  const { status, disposition, assignee_id, risk_min, risk_max, source_system, typology, created_from, created_to, q } =
    query;
  const statsQuery = useQuery({
    queryKey: [
      "caseStats",
      { status, disposition, assignee_id, risk_min, risk_max, source_system, typology, created_from, created_to, q },
    ],
    queryFn: () =>
      getCaseStats(
        { status, disposition, assignee_id, risk_min, risk_max, source_system, typology, created_from, created_to, q },
        token,
      ),
    retry: false,
  });

  const s = statsQuery.data;

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-md border border-border bg-surface-sunken px-3 py-2">
      {s ? (
        <>
          <Chip label="cases" value={s.total} />
          <Chip label="open" value={s.by_status["Open"] ?? 0} />
          <Chip label="in progress" value={s.by_status["In Progress"] ?? 0} />
          <Chip label="avg risk" value={s.avg_risk} emphasis={s.avg_risk >= 60 ? "warn" : undefined} />
          <Chip
            label={`≥${s.high_risk_threshold}`}
            value={s.high_risk}
            emphasis={s.high_risk > 0 ? "danger" : undefined}
          />
          <Chip label="unassigned" value={s.unassigned} />
        </>
      ) : (
        <span className="text-2xs uppercase tracking-wider text-ink-tertiary">
          {statsQuery.isError ? "Summary unavailable" : "Loading summary…"}
        </span>
      )}
    </div>
  );
}
