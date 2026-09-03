import { useQuery } from "@tanstack/react-query";
import { getCaseStats, type CaseQuery } from "../../api/cases";
import { useAuth } from "../../auth/AuthContext";
import { StatCard } from "../ui/StatCard";

function LayersIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M10 3 3 6.5 10 10l7-3.5L10 3Z" strokeLinejoin="round" />
      <path d="M3 10.5 10 14l7-3.5M3 13.5 10 17l7-3.5" strokeLinejoin="round" />
    </svg>
  );
}
function GaugeIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M4 15a7 7 0 1 1 12 0" strokeLinecap="round" />
      <path d="M10 10l3-3" strokeLinecap="round" />
    </svg>
  );
}
function FlagIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M5 3v14M5 4h9l-2 3 2 3H5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function UserIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="10" cy="7" r="3" />
      <path d="M4.5 16a5.5 5.5 0 0 1 11 0" strokeLinecap="round" />
    </svg>
  );
}

export function CasesSummary({ query }: { query: CaseQuery }) {
  const { token } = useAuth();
  const { status, disposition, assignee_id, risk_min, risk_max, source_system, typology, created_from, created_to, q } =
    query;
  const key = { status, disposition, assignee_id, risk_min, risk_max, source_system, typology, created_from, created_to, q };
  const statsQuery = useQuery({
    queryKey: ["caseStats", key],
    queryFn: () => getCaseStats(key, token),
    retry: false,
  });
  const s = statsQuery.data;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard
        icon={<LayersIcon />}
        label="Open cases"
        value={s ? (s.by_status["Open"] ?? 0) : "—"}
        seed={1}
        tone="info"
      />
      <StatCard
        icon={<GaugeIcon />}
        label="Average risk"
        value={s ? s.avg_risk : "—"}
        seed={4}
        tone={s && s.avg_risk >= 60 ? "danger" : "accent"}
      />
      <StatCard
        icon={<FlagIcon />}
        label={s ? `Risk ≥ ${s.high_risk_threshold}` : "High risk"}
        value={s ? s.high_risk : "—"}
        seed={7}
        tone="danger"
      />
      <StatCard
        icon={<UserIcon />}
        label="Unassigned"
        value={s ? s.unassigned : "—"}
        seed={2}
        tone="accent"
      />
    </div>
  );
}
