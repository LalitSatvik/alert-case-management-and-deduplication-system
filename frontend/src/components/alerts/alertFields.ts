import type { AlertOut } from "../../api/types";

/** The normalized fields worth showing / diffing for an alert. Empty values dropped. */
export function alertFields(a: AlertOut): Record<string, unknown> {
  const out: Record<string, unknown> = {
    external_alert_id: a.external_alert_id,
    source_system: a.source_system,
    event_time: a.event_time,
    amount: `${a.amount} ${a.currency}`,
    direction: a.direction,
    customer_ref: a.customer_ref,
    account_ref: a.account_ref,
    counterparty_ref: a.counterparty_ref,
    merchant_name: a.merchant_name,
    mcc: a.mcc,
    device_id: a.device_id,
    ip_address: a.ip_address,
    session_id: a.session_id,
    risk_score: a.risk_score,
    rule_codes: a.rule_codes?.length ? a.rule_codes.join(", ") : undefined,
    typologies: a.typologies?.length ? a.typologies.join(", ") : undefined,
  };
  for (const k of Object.keys(out)) {
    if (out[k] == null || out[k] === "") delete out[k];
  }
  return out;
}
