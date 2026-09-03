import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UserOut } from "../../api/types";
import { assignCase, transitionCase, type TransitionBody } from "../../api/cases";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ALLOWED, DISPOSITIONS } from "../../lib/lifecycle";
import { RoleGate } from "../RoleGate";
import { Button } from "../ui/Button";
import { Select, TextInput, FieldLabel } from "../ui/Field";
import { AssigneePicker } from "../cases/AssigneePicker";
import { toast } from "../ui/Toaster";
import { cn } from "../ui/cn";

export function ActionToolbar({
  caseId,
  status,
  version,
  assigneeId,
  assigneeEmail,
  users,
}: {
  caseId: string;
  status: string;
  version?: number;
  assigneeId?: string | null;
  assigneeEmail?: string | null;
  users: UserOut[];
}) {
  const { token, principal } = useAuth();
  const qc = useQueryClient();
  const targets = ALLOWED[status] ?? [];

  const [pending, setPending] = useState<string | null>(null);
  const [disposition, setDisposition] = useState(DISPOSITIONS[0]);
  const [reason, setReason] = useState("");
  const [flash, setFlash] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["case", caseId] });
    qc.invalidateQueries({ queryKey: ["cases"] });
    qc.invalidateQueries({ queryKey: ["caseStats"] });
  };

  const move = useMutation({
    mutationFn: (body: TransitionBody) => transitionCase(caseId, body, token, version),
    onSuccess: (_d, body) => {
      setPending(null);
      setReason("");
      setFlash(true);
      setTimeout(() => setFlash(false), 900);
      toast.success(`Case moved to ${body.to}`);
      invalidate();
    },
    onError: (err) => {
      const detail = err instanceof ApiError ? (err.code ?? err.detail) : undefined;
      if (detail === "stale_case_version") {
        toast.error("This case changed since you loaded it. Reload to get the latest.");
      } else {
        toast.error(err instanceof ApiError ? (err.detail ?? err.message) : "Transition failed");
      }
    },
  });

  const assign = useMutation({
    mutationFn: (id: string | null) => assignCase(caseId, id, token),
    onSuccess: () => {
      toast.success("Assignee updated");
      invalidate();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? (err.detail ?? err.message) : "Could not assign"),
  });

  const needsDisposition = pending === "Closed";
  const needsReason = pending != null && status === "Closed"; // reopen

  function confirm() {
    if (!pending) return;
    if (needsReason && !reason.trim()) return;
    move.mutate({
      to: pending,
      disposition: needsDisposition ? disposition : undefined,
      reason: reason.trim() || undefined,
    });
  }

  return (
    <RoleGate allow={["analyst", "admin"]}>
      <div className="space-y-2">
        <FieldLabel>Actions</FieldLabel>

        <div className="flex flex-wrap gap-1.5">
          {targets.map((to) => {
            const danger = to === "Closed";
            const armed = pending === to;
            return (
              <Button
                key={to}
                size="sm"
                variant={danger ? "danger" : armed ? "primary" : "default"}
                className={cn(flash && !armed && "ring-1 ring-success")}
                disabled={move.isPending}
                onClick={() => {
                  if ((to === "Closed" || status === "Closed") && !armed) setPending(to);
                  else if (armed) confirm();
                  else move.mutate({ to });
                }}
              >
                {armed ? "Confirm" : to === "Closed" ? "Close case" : `Move to ${to}`}
              </Button>
            );
          })}
          {targets.length === 0 && (
            <span className="text-xs text-ink-tertiary">No transitions available.</span>
          )}
          {pending && (
            <Button size="sm" variant="ghost" onClick={() => setPending(null)}>
              Cancel
            </Button>
          )}
        </div>

        {pending && (
          <div className="space-y-1.5 rounded-md border border-border bg-surface-sunken p-2">
            {needsDisposition && (
              <label className="flex flex-col gap-1">
                <FieldLabel>Disposition (required)</FieldLabel>
                <Select
                  value={disposition}
                  onChange={(e) => setDisposition(e.target.value)}
                  className="h-8"
                >
                  {DISPOSITIONS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </Select>
              </label>
            )}
            <label className="flex flex-col gap-1">
              <FieldLabel>{needsReason ? "Reason (required)" : "Reason"}</FieldLabel>
              <TextInput
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={needsReason ? "Why reopen?" : "Optional note"}
                className="h-8"
              />
            </label>
          </div>
        )}

        <div className="pt-1">
          <FieldLabel>Assignee</FieldLabel>
          <div className="mt-1">
            <AssigneePicker
              users={users}
              value={assigneeId ?? "unassigned"}
              resolvedLabel={assigneeEmail ?? (assigneeId ? "Assigned" : "Unassigned")}
              principalId={principal?.id}
              onChange={(v) => {
                if (v === "unassigned" || v === "all") assign.mutate(null);
                else if (v === "me") assign.mutate(principal?.id ?? null);
                else assign.mutate(v);
              }}
            />
          </div>
        </div>
      </div>
    </RoleGate>
  );
}
