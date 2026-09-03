import { useState } from "react";
import type { UserOut } from "../../api/types";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/Popover";
import { buttonClass } from "../ui/Button";
import { TextInput } from "../ui/Field";
import { cn } from "../ui/cn";

export function AssigneePicker({
  users,
  value,
  resolvedLabel,
  principalId,
  onChange,
}: {
  users: UserOut[];
  value: string;
  resolvedLabel: string;
  principalId?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  const filtered = users.filter(
    (u) =>
      u.id !== principalId &&
      (u.email.toLowerCase().includes(q.toLowerCase()) ||
        u.display_name.toLowerCase().includes(q.toLowerCase())),
  );

  const pick = (v: string) => {
    onChange(v);
    setOpen(false);
    setQ("");
  };

  const Row = ({ v, label }: { v: string; label: string }) => (
    <button
      type="button"
      onClick={() => pick(v)}
      className={cn(
        "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface-hover",
        value === v ? "text-ink" : "text-ink-secondary",
      )}
    >
      <span className="truncate">{label}</span>
      {value === v && <span className="text-accent">✓</span>}
    </button>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger className={buttonClass("default", "sm")}>
        <span className="text-2xs uppercase tracking-wider text-ink-tertiary">Assignee</span>
        <span className="ml-1.5 max-w-[10rem] truncate">{resolvedLabel}</span>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-1.5">
        <TextInput
          autoFocus
          placeholder="Search people…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="mb-1 h-8"
        />
        <div className="max-h-64 overflow-auto">
          <Row v="all" label="Anyone" />
          {principalId && <Row v="me" label="Me" />}
          <Row v="unassigned" label="Unassigned" />
          <div className="my-1 h-px bg-border" />
          {filtered.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => pick(u.id)}
              className={cn(
                "flex w-full flex-col rounded-sm px-2 py-1.5 text-left transition-colors hover:bg-surface-hover",
                value === u.id ? "text-ink" : "text-ink-secondary",
              )}
            >
              <span className="truncate text-sm">{u.display_name}</span>
              <span className="truncate font-mono text-2xs text-ink-tertiary">{u.email}</span>
            </button>
          ))}
          {filtered.length === 0 && q && (
            <p className="px-2 py-2 text-xs text-ink-tertiary">No match</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
