import { useState } from "react";
import type { AlertOut } from "../../api/types";
import { Dialog, DialogContent } from "../ui/Dialog";
import { Select } from "../ui/Field";
import { RecordDiff } from "../ui/Diff";
import { alertFields } from "./alertFields";

export function AlertDiffDialog({
  baseId,
  alerts,
  onClose,
}: {
  baseId: string | null;
  alerts: AlertOut[];
  onClose: () => void;
}) {
  const base = alerts.find((a) => a.id === baseId) ?? null;
  const others = alerts.filter((a) => a.id !== baseId);
  const [picked, setPicked] = useState<string>("");
  const otherId =
    picked && picked !== baseId && others.some((a) => a.id === picked)
      ? picked
      : (others[0]?.id ?? "");
  const other = alerts.find((a) => a.id === otherId) ?? null;
  const setOtherId = setPicked;

  return (
    <Dialog open={baseId != null} onOpenChange={(o) => !o && onClose()}>
      {base && (
        <DialogContent
          title="Compare alerts"
          description={`${base.external_alert_id} against another alert in this case`}
          width="xl"
        >
          <div className="space-y-3 p-4">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
                Compare to
              </span>
              <Select
                value={otherId}
                onChange={(e) => setOtherId(e.target.value)}
                className="!w-64"
              >
                {others.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.external_alert_id}
                  </option>
                ))}
              </Select>
            </label>

            {other ? (
              <>
                <div>
                  <p className="mb-1 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
                    Normalized fields
                  </p>
                  <RecordDiff
                    before={alertFields(base)}
                    after={alertFields(other)}
                    emptyLabel="These alerts have identical normalized fields."
                  />
                </div>
                {(Object.keys(base.raw_payload ?? {}).length > 0 ||
                  Object.keys(other.raw_payload ?? {}).length > 0) && (
                  <div>
                    <p className="mb-1 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
                      Raw payload
                    </p>
                    <RecordDiff
                      before={base.raw_payload}
                      after={other.raw_payload}
                      emptyLabel="Payloads match."
                    />
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-ink-tertiary">No other alert to compare.</p>
            )}
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
