import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CaseListItem, UserOut } from "../../api/types";
import { assignCase, transitionCase } from "../../api/cases";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ALLOWED } from "../../lib/lifecycle";
import { Button } from "../ui/Button";
import { AssigneePicker } from "./AssigneePicker";
import { toast } from "../ui/Toaster";

// Targets that need no disposition/reason — the only ones safe to apply in bulk.
const SIMPLE_TARGETS = new Set(["In Progress", "Pending Info"]);

export function BulkActionBar({
  selected,
  users,
  onDone,
}: {
  selected: CaseListItem[];
  users: UserOut[];
  onDone: () => void;
}) {
  const { token, principal } = useAuth();
  const qc = useQueryClient();

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["cases"] });
    qc.invalidateQueries({ queryKey: ["caseStats"] });
  };

  const move = useMutation({
    mutationFn: async (to: string) => {
      await Promise.all(selected.map((c) => transitionCase(c.id, { to }, token)));
    },
    onSuccess: (_data, to) => {
      toast.success(`Moved ${selected.length} case${selected.length > 1 ? "s" : ""} to ${to}`);
      invalidate();
      onDone();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? (err.detail ?? err.message) : "Some cases could not be moved"),
  });

  const assign = useMutation({
    mutationFn: async (assigneeId: string | null) => {
      await Promise.all(selected.map((c) => assignCase(c.id, assigneeId, token)));
    },
    onSuccess: () => {
      toast.success(`Reassigned ${selected.length} case${selected.length > 1 ? "s" : ""}`);
      invalidate();
      onDone();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? (err.detail ?? err.message) : "Some cases could not be reassigned"),
  });

  // Legal simple targets = intersection across every selected case's status.
  const statuses = [...new Set(selected.map((c) => c.status))];
  const legalTargets = [...SIMPLE_TARGETS].filter((t) =>
    statuses.every((s) => (ALLOWED[s] ?? []).includes(t)),
  );
  const partialTargets = [...SIMPLE_TARGETS].filter(
    (t) => !legalTargets.includes(t) && selected.some((c) => (ALLOWED[c.status] ?? []).includes(t)),
  );

  const busy = move.isPending || assign.isPending;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-accent-border bg-accent-subtle px-3 py-2">
      <span className="font-mono text-sm font-semibold tabular-nums text-ink">{selected.length}</span>
      <span className="text-2xs uppercase tracking-wider text-ink-secondary">selected</span>

      <span className="mx-1 h-4 w-px bg-border" />

      {legalTargets.map((t) => (
        <Button key={t} size="sm" variant="default" disabled={busy} onClick={() => move.mutate(t)}>
          Move to {t}
        </Button>
      ))}
      {partialTargets.map((t) => {
        const n = selected.filter((c) => (ALLOWED[c.status] ?? []).includes(t)).length;
        return (
          <span key={t} className="text-2xs text-ink-tertiary">
            {n} of {selected.length} can move to {t}
          </span>
        );
      })}

      <AssigneePicker
        users={users}
        value="all"
        resolvedLabel="Reassign…"
        principalId={principal?.id}
        onChange={(v) => {
          if (v === "unassigned" || v === "all") assign.mutate(null);
          else if (v === "me") assign.mutate(principal?.id ?? null);
          else assign.mutate(v);
        }}
      />

      <Button size="sm" variant="ghost" disabled={busy} onClick={onDone}>
        Clear
      </Button>
    </div>
  );
}
