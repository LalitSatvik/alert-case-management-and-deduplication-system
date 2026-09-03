const ALL_STATUSES = ["Open", "In Progress", "Pending Info", "Closed", "Merged"];

const SORTS: { value: string; label: string }[] = [
  { value: "-risk_score", label: "Highest risk" },
  { value: "-created_at", label: "Newest" },
  { value: "oldest_alert", label: "Oldest alert" },
];

const fieldLabel = "flex flex-col gap-1 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary";
const control =
  "min-h-control rounded-md border border-border bg-surface px-2.5 text-sm font-normal normal-case tracking-normal text-ink shadow-xs transition-colors hover:border-border-strong focus-visible:border-accent";

export interface CaseFiltersProps {
  statuses: string[];
  onToggleStatus: (s: string) => void;
  assignee: string;
  onAssignee: (v: string) => void;
  riskMin: number | null;
  onRiskMin: (v: number | null) => void;
  q: string;
  onQ: (v: string) => void;
  sort: string;
  onSort: (v: string) => void;
}

export function CaseFilters(props: CaseFiltersProps) {
  const { statuses, onToggleStatus, assignee, onAssignee, riskMin, onRiskMin, q, onQ, sort, onSort } =
    props;

  return (
    <div className="space-y-4 rounded-lg border border-border bg-surface p-4 shadow-xs">
      <div className="flex flex-wrap items-center gap-2">
        {ALL_STATUSES.map((s) => {
          const active = statuses.includes(s);
          return (
            <button
              key={s}
              type="button"
              aria-pressed={active}
              onClick={() => onToggleStatus(s)}
              className={`inline-flex min-h-control items-center gap-1 rounded-full border px-3.5 text-xs font-medium transition-colors duration-2 ${
                active
                  ? "border-accent bg-accent pl-2.5 text-accent-fg shadow-xs"
                  : "border-border bg-surface text-ink-secondary hover:border-border-strong hover:text-ink"
              }`}
            >
              <span
                aria-hidden="true"
                className={`grid h-3 w-3 place-items-center transition-[opacity,transform] duration-2 ${
                  active ? "scale-100 opacity-100" : "hidden scale-75 opacity-0"
                }`}
              >
                <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M2.5 6.5 5 9l4.5-5.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              {s}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <label className={fieldLabel}>
          Assignee
          <select value={assignee} onChange={(e) => onAssignee(e.target.value)} className={control}>
            <option value="all">Anyone</option>
            <option value="me">Me</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </label>

        <label className={fieldLabel}>
          Min risk
          <input
            type="number"
            name="risk_min"
            inputMode="numeric"
            autoComplete="off"
            min={0}
            max={100}
            value={riskMin ?? ""}
            onChange={(e) => onRiskMin(e.target.value === "" ? null : Number(e.target.value))}
            className={`${control} w-24 font-mono`}
          />
        </label>

        <label className={`${fieldLabel} flex-1`}>
          Search
          <input
            type="search"
            name="q"
            autoComplete="off"
            spellCheck={false}
            value={q}
            placeholder="e.g. CASE-1042, structuring, ACME Ltd…"
            onChange={(e) => onQ(e.target.value)}
            className={`${control} w-full`}
          />
        </label>

        <label className={fieldLabel}>
          Sort
          <select value={sort} onChange={(e) => onSort(e.target.value)} className={control}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
