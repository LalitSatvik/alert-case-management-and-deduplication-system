import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { transitionCase, type TransitionBody } from "../api/cases";
import { ALLOWED, DISPOSITIONS } from "../lib/lifecycle";
import { useAuth } from "../auth/AuthContext";
import { RoleGate } from "./RoleGate";

const selectCls =
  "min-h-control rounded-md border border-border bg-surface px-2.5 text-sm text-ink shadow-xs transition-colors hover:border-border-strong focus-visible:border-accent";
const inputCls = selectCls;

export function TransitionControls({
  caseId,
  status,
  version,
}: {
  caseId: string;
  status: string;
  version?: number;
}) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [disposition, setDisposition] = useState(DISPOSITIONS[0]);
  const [reason, setReason] = useState("");

  const next = ALLOWED[status] ?? [];

  const mut = useMutation({
    mutationFn: (body: TransitionBody) => transitionCase(caseId, body, token, version),
    onSuccess: () => {
      setReason("");
      qc.invalidateQueries({ queryKey: ["case", caseId] });
    },
  });

  if (next.length === 0) return null;

  const primaryBtn =
    "inline-flex min-h-control items-center rounded-md bg-accent px-3.5 text-sm font-medium text-accent-fg shadow-xs transition-colors hover:bg-accent-hover disabled:opacity-40";
  const dangerBtn =
    "inline-flex min-h-control items-center rounded-md border border-danger-border bg-danger-subtle px-3.5 text-sm font-medium text-danger-subtle-fg transition-colors hover:border-danger disabled:opacity-40";

  function renderAction(to: string) {
    if (to === "Closed") {
      return (
        <div key={to} className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Disposition"
            value={disposition}
            onChange={(e) => setDisposition(e.target.value)}
            className={selectCls}
          >
            {DISPOSITIONS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <input
            aria-label="Reason"
            name="close_reason"
            autoComplete="off"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason, e.g. confirmed duplicate…"
            className={inputCls}
          />
          <button
            type="button"
            className={dangerBtn}
            disabled={mut.isPending}
            onClick={() => mut.mutate({ to, disposition, reason: reason || undefined })}
          >
            Close case
          </button>
        </div>
      );
    }

    if (status === "Closed") {
      return (
        <div key={to} className="flex flex-wrap items-center gap-2">
          <input
            aria-label="Reason for reopening"
            name="reopen_reason"
            autoComplete="off"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for reopening, e.g. new alert linked…"
            className={inputCls}
          />
          <button
            type="button"
            className={primaryBtn}
            disabled={mut.isPending || !reason.trim()}
            onClick={() => mut.mutate({ to, reason: reason.trim() })}
          >
            {`Move to ${to}`}
          </button>
        </div>
      );
    }

    return (
      <button
        key={to}
        type="button"
        className={primaryBtn}
        disabled={mut.isPending}
        onClick={() => mut.mutate({ to })}
      >
        {`Move to ${to}`}
      </button>
    );
  }

  return (
    <RoleGate allow={["analyst", "admin"]}>
      <div className="flex flex-wrap items-center gap-2">
        {next.map((to) => renderAction(to))}
        {mut.isError && (
          <span role="alert" className="text-sm text-ink-danger">
            {mut.error instanceof ApiError
              ? (mut.error.detail ?? mut.error.message)
              : "Transition failed"}
          </span>
        )}
      </div>
    </RoleGate>
  );
}
