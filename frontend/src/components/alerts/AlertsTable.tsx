import { useState } from "react";
import type { AlertOut } from "../../api/types";
import { RiskScore } from "../ui/RiskScore";
import { Badge } from "../ui/Badge";
import { JsonView } from "../ui/JsonView";
import { cn } from "../ui/cn";
import { relativeTime } from "../../lib/format";
import { GroupingBadge } from "./GroupingBadge";
import { AlertDiffDialog } from "./AlertDiffDialog";
import { alertFields } from "./alertFields";

// One template drives the header and every row so columns stay aligned.
const GRID =
  "grid grid-cols-[1.25rem_4.5rem_minmax(9rem,1.4fr)_6.5rem_minmax(7rem,1fr)_minmax(8rem,1fr)_minmax(7rem,1fr)_minmax(6rem,1fr)_auto_4.5rem_4.75rem] items-center gap-x-3";

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 12 12"
      className={cn("h-3 w-3 shrink-0 transition-transform duration-2", open && "rotate-90")}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
    >
      <path d="M4.5 2.5 8 6l-3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Stacked({ top, bottom }: { top?: string | null; bottom?: string | null }) {
  if (!top && !bottom) return <span className="text-ink-tertiary">—</span>;
  return (
    <span className="flex min-w-0 flex-col leading-tight">
      <span className="truncate font-mono">{top ?? "—"}</span>
      {bottom && <span className="truncate font-mono text-2xs text-ink-tertiary">{bottom}</span>}
    </span>
  );
}

const HEAD = "text-2xs font-semibold uppercase tracking-wider text-ink-tertiary";

export function AlertsTable({ alerts }: { alerts: AlertOut[] }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [compareBase, setCompareBase] = useState<string | null>(null);

  const toggle = (id: string) =>
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  if (alerts.length === 0) {
    return <p className="text-sm text-ink-tertiary">No alerts in this case.</p>;
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border border-border bg-surface">
        <div className="min-w-[64rem]">
          <div
            className={cn(
              GRID,
              "sticky top-0 z-10 border-b border-border bg-surface-sunken px-cell-x py-cell-y",
            )}
          >
            <span />
            <span className={cn(HEAD, "text-right")}>Risk</span>
            <span className={HEAD}>Alert</span>
            <span className={cn(HEAD, "text-right")}>Amount</span>
            <span className={HEAD}>Customer / CP</span>
            <span className={HEAD}>Merchant / MCC</span>
            <span className={HEAD}>Device / IP</span>
            <span className={HEAD}>Typologies</span>
            <span className={HEAD}>Linking</span>
            <span className={cn(HEAD, "text-right")}>Age</span>
            <span />
          </div>

          {alerts.map((a) => {
            const isOpen = open.has(a.id);
            return (
              <div key={a.id} className="border-b border-border-subtle last:border-0">
                <div
                  role="button"
                  tabIndex={0}
                  aria-expanded={isOpen}
                  onClick={() => toggle(a.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggle(a.id);
                    }
                  }}
                  className={cn(
                    GRID,
                    "cursor-pointer px-cell-x py-cell-y leading-tight transition-colors hover:bg-surface-hover",
                  )}
                >
                  <Chevron open={isOpen} />
                  <span className="flex justify-end">
                    {a.risk_score != null ? (
                      <RiskScore score={a.risk_score} size="sm" />
                    ) : (
                      <span className="text-ink-tertiary">—</span>
                    )}
                  </span>
                  <span className="flex min-w-0 items-baseline gap-2">
                    <span className="truncate font-mono font-medium text-ink">
                      {a.external_alert_id}
                    </span>
                    {a.source_system && (
                      <span className="shrink-0 text-2xs text-ink-tertiary">{a.source_system}</span>
                    )}
                  </span>
                  <span className="text-right font-mono tabular-nums">
                    <span className="block truncate">{a.amount}</span>
                    <span className="block text-2xs text-ink-tertiary">
                      {a.currency}
                      {a.direction ? ` · ${a.direction}` : ""}
                    </span>
                  </span>
                  <Stacked top={a.customer_ref} bottom={a.counterparty_ref} />
                  <Stacked top={a.merchant_name} bottom={a.mcc} />
                  <Stacked top={a.device_id} bottom={a.ip_address} />
                  <span className="flex flex-wrap gap-1">
                    {(a.typologies ?? []).map((t) => (
                      <Badge key={t} tone="warning">
                        {t}
                      </Badge>
                    ))}
                  </span>
                  <span onClick={(e) => e.stopPropagation()}>
                    <GroupingBadge grouping={a.grouping} />
                  </span>
                  <span className="text-right text-ink-tertiary">
                    {a.event_time ? relativeTime(a.event_time) : "—"}
                  </span>
                  <span className="flex justify-end" onClick={(e) => e.stopPropagation()}>
                    {alerts.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setCompareBase(a.id)}
                        className="rounded-sm px-1.5 py-0.5 text-2xs font-medium text-ink-tertiary transition-colors hover:bg-surface-hover hover:text-ink"
                      >
                        Compare
                      </button>
                    )}
                  </span>
                </div>

                <div
                  className="grid transition-[grid-template-rows] duration-3 ease-out motion-reduce:transition-none"
                  style={{ gridTemplateRows: isOpen ? "1fr" : "0fr" }}
                >
                  <div className="overflow-hidden">
                    {isOpen && (
                      <div className="bg-surface-sunken px-cell-x pb-3 pt-1">
                        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
                          {Object.entries(alertFields(a)).map(([k, v]) => (
                            <div key={k} className="min-w-0">
                              <dt className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
                                {k}
                              </dt>
                              <dd className="truncate font-mono text-xs text-ink">{String(v)}</dd>
                            </div>
                          ))}
                        </dl>
                        <p className="mb-1 mt-3 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
                          Raw payload
                        </p>
                        <JsonView value={a.raw_payload} />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <AlertDiffDialog baseId={compareBase} alerts={alerts} onClose={() => setCompareBase(null)} />
    </>
  );
}
