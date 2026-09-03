import type { ReactNode } from "react";
import type { AlertOut } from "../api/types";
import { GroupingRationale } from "./GroupingRationale";
import { relativeTime } from "../lib/format";

function Field({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <dt className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">{label}</dt>
      <dd className={`mt-0.5 text-ink ${mono ? "font-mono text-[0.8125rem]" : ""}`}>{value}</dd>
    </div>
  );
}

export function AlertCard({ alert }: { alert: AlertOut }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-xs transition-shadow duration-3 hover:shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className="font-mono text-[0.9375rem] font-medium text-ink">
            {alert.external_alert_id}
          </span>
          {alert.source_system && (
            <span className="ml-2 rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-ink-secondary">
              {alert.source_system}
            </span>
          )}
          {alert.event_time && (
            <span className="ml-2 text-xs text-ink-tertiary">{relativeTime(alert.event_time)}</span>
          )}
        </div>
        <GroupingRationale grouping={alert.grouping} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <Field label="Amount" value={`${alert.amount} ${alert.currency}`} mono />
        <Field label="Direction" value={alert.direction} />
        <Field label="Customer" value={alert.customer_ref} mono />
        <Field label="Counterparty" value={alert.counterparty_ref} mono />
        <Field label="Merchant" value={alert.merchant_name} />
        <Field label="MCC" value={alert.mcc} mono />
        <Field label="Device" value={alert.device_id} mono />
        <Field label="IP" value={alert.ip_address} mono />
        <Field
          label="Rules"
          value={alert.rule_codes && alert.rule_codes.length ? alert.rule_codes.join(", ") : null}
          mono
        />
        <Field
          label="Typologies"
          value={alert.typologies && alert.typologies.length ? alert.typologies.join(", ") : null}
        />
      </dl>

      <details className="group mt-4">
        <summary className="-mx-2 inline-flex min-h-control cursor-pointer select-none items-center gap-1.5 rounded-sm px-2 text-sm text-ink-secondary transition-colors hover:text-ink">
          <svg
            aria-hidden="true"
            viewBox="0 0 12 12"
            className="h-3 w-3 transition-transform duration-2 group-open:rotate-90"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
          >
            <path d="M4.5 2.5 8 6l-3.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Raw payload
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-md border border-code-border bg-code-bg p-3 font-mono text-xs leading-relaxed text-code-fg">
          {JSON.stringify(alert.raw_payload ?? {}, null, 2)}
        </pre>
      </details>
    </div>
  );
}
