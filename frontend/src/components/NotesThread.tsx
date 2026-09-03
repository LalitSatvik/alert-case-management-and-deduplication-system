import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { NoteOut } from "../api/types";
import { ApiError } from "../api/client";
import { addNote, retractNote } from "../api/cases";
import { useAuth } from "../auth/AuthContext";
import { RoleGate } from "./RoleGate";
import { relativeTime } from "../lib/format";

function errText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? (err.detail ?? err.message) : fallback;
}

export function NotesThread({ caseId, notes }: { caseId: string; notes: NoteOut[] }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [body, setBody] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["case", caseId] });

  const add = useMutation({
    mutationFn: () => addNote(caseId, body.trim(), token),
    onSuccess: () => {
      setBody("");
      invalidate();
    },
  });

  const retract = useMutation({
    mutationFn: (vars: { noteId: string; reason: string }) =>
      retractNote(caseId, vars.noteId, vars.reason, token),
    onSuccess: invalidate,
  });

  const sorted = [...(notes ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (body.trim()) add.mutate();
  }

  return (
    <div className="space-y-4">
      <ul className="u-stagger space-y-3">
        {sorted.map((n) => (
          <li key={n.id} className="rounded-lg border border-border bg-surface p-3 shadow-xs">
            <p
              className={
                n.retracted
                  ? "text-sm text-ink-tertiary line-through"
                  : "text-sm text-ink"
              }
            >
              {n.body}
            </p>
            <div className="mt-1.5 flex items-center gap-2 text-xs text-ink-tertiary">
              <span className="font-mono">{n.author_id}</span>
              <span aria-hidden="true">·</span>
              <span>{relativeTime(n.created_at)}</span>
            </div>
            {n.retracted && (
              <p className="mt-1 text-xs text-ink-danger">
                Retracted{n.retraction_reason ? `: ${n.retraction_reason}` : ""}
              </p>
            )}
            {!n.retracted && (
              <RoleGate allow={["analyst", "admin"]}>
                <button
                  type="button"
                  className="mt-1 -mx-2 inline-flex min-h-control items-center rounded-sm px-2 text-xs font-medium text-ink-danger hover:underline"
                  onClick={() => {
                    const reason = window.prompt("Reason for retraction?");
                    if (reason && reason.trim()) {
                      retract.mutate({ noteId: n.id, reason: reason.trim() });
                    }
                  }}
                >
                  Retract
                </button>
              </RoleGate>
            )}
          </li>
        ))}
        {sorted.length === 0 && <li className="text-sm text-ink-tertiary">No notes yet.</li>}
      </ul>

      {retract.isError && (
        <p role="alert" className="text-sm text-ink-danger">
          {errText(retract.error, "Could not retract note")}
        </p>
      )}

      <RoleGate allow={["analyst", "admin"]}>
        <form onSubmit={submit} className="space-y-2">
          <textarea
            aria-label="Add a note"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-border bg-surface p-2.5 text-sm text-ink shadow-xs transition-colors placeholder:text-ink-muted hover:border-border-strong focus-visible:border-accent"
            placeholder="Add an investigation note…"
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!body.trim() || add.isPending}
              className="inline-flex min-h-control items-center rounded-md bg-accent px-3.5 text-sm font-medium text-accent-fg shadow-xs transition-colors hover:bg-accent-hover disabled:opacity-40"
            >
              Add note
            </button>
            {add.isError && (
              <span role="alert" className="text-sm text-ink-danger">
                {errText(add.error, "Could not add note")}
              </span>
            )}
          </div>
        </form>
      </RoleGate>
    </div>
  );
}
