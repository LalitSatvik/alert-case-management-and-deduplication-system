import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { UserOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  CASE_STATUSES,
  DISPOSITIONS,
  SOURCE_SYSTEMS,
  TYPOLOGIES,
  activeFilterCount,
  readFilterState,
} from "../lib/caseFilters";
import { AssigneePicker } from "./cases/AssigneePicker";
import { SavedViewsMenu } from "./cases/SavedViewsMenu";
import { Button } from "./ui/Button";
import { FieldLabel, Select, TextInput } from "./ui/Field";
import { cn } from "./ui/cn";

export function CaseFilters({ users }: { users: UserOut[] }) {
  const { principal } = useAuth();
  const [sp, setSp] = useSearchParams();
  const state = readFilterState(sp);
  const [advanced, setAdvanced] = useState(activeFilterCount(state) > 0);
  const [qInput, setQInput] = useState(state.q);

  useEffect(() => {
    if (qInput === state.q) return;
    const t = setTimeout(() => {
      setSp(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (qInput) n.set("q", qInput);
          else n.delete("q");
          return n;
        },
        { replace: true },
      );
    }, 300);
    return () => clearTimeout(t);
  }, [qInput, state.q, setSp]);

  function mutate(fn: (n: URLSearchParams) => void, replace = false) {
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev);
        fn(n);
        return n;
      },
      { replace },
    );
  }

  const setMulti = (key: string, values: string[]) =>
    mutate((n) => {
      n.delete(key);
      values.forEach((v) => n.append(key, v));
    });

  const setSingle = (key: string, value: string) =>
    mutate((n) => (value ? n.set(key, value) : n.delete(key)));

  const activeCount = activeFilterCount(state);
  const anyActive =
    activeCount > 0 || state.statuses.length > 0 || state.assignee !== "all" || state.q !== "";

  const usersById = useMemo(() => new Map(users.map((u) => [u.id, u])), [users]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1">
          {CASE_STATUSES.map((s) => {
            const on = state.statuses.includes(s);
            return (
              <button
                key={s}
                type="button"
                aria-pressed={on}
                onClick={() =>
                  setMulti(
                    "status",
                    on ? state.statuses.filter((x) => x !== s) : [...state.statuses, s],
                  )
                }
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  on
                    ? "border-primary bg-primary text-primary-fg"
                    : "border-border bg-surface text-ink-secondary hover:border-border-strong hover:text-ink",
                )}
              >
                {s}
              </button>
            );
          })}
        </div>

        <AssigneePicker
          users={users}
          value={state.assignee}
          resolvedLabel={
            state.assignee === "all"
              ? "Anyone"
              : state.assignee === "me"
                ? "Me"
                : state.assignee === "unassigned"
                  ? "Unassigned"
                  : (usersById.get(state.assignee)?.email ?? "Unknown")
          }
          principalId={principal?.id}
          onChange={(v) => setSingle("assignee", v === "all" ? "" : v)}
        />

        <TextInput
          type="search"
          aria-label="Search cases"
          placeholder="CASE-1042, structuring, merchant…"
          value={qInput}
          spellCheck={false}
          onChange={(e) => setQInput(e.target.value)}
          className="h-8 !w-64"
        />

        <Button
          size="sm"
          variant={advanced ? "primary" : "default"}
          onClick={() => setAdvanced((v) => !v)}
          aria-expanded={advanced}
        >
          Advanced{activeCount > 0 ? ` · ${activeCount}` : ""}
        </Button>

        <SavedViewsMenu users={users} />

        {anyActive && (
          <Button size="sm" variant="ghost" onClick={() => setSp({}, { replace: true })}>
            Clear
          </Button>
        )}
      </div>

      {advanced && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-2xl border border-border bg-surface p-4 shadow-xs sm:grid-cols-3 lg:grid-cols-6">
          <label className="flex flex-col gap-1">
            <FieldLabel>Risk min</FieldLabel>
            <TextInput
              type="number"
              min={0}
              max={100}
              inputMode="numeric"
              className="h-8 font-mono"
              value={state.riskMin ?? ""}
              onChange={(e) => setSingle("risk_min", e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <FieldLabel>Risk max</FieldLabel>
            <TextInput
              type="number"
              min={0}
              max={100}
              inputMode="numeric"
              className="h-8 font-mono"
              value={state.riskMax ?? ""}
              onChange={(e) => setSingle("risk_max", e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <FieldLabel>Typology</FieldLabel>
            <Select
              className="h-8"
              value={state.typology}
              onChange={(e) => setSingle("typology", e.target.value)}
            >
              <option value="">Any</option>
              {TYPOLOGIES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1">
            <FieldLabel>Source system</FieldLabel>
            <Select
              className="h-8"
              value={state.sourceSystem}
              onChange={(e) => setSingle("source_system", e.target.value)}
            >
              <option value="">Any</option>
              {SOURCE_SYSTEMS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1">
            <FieldLabel>Created after</FieldLabel>
            <TextInput
              type="date"
              className="h-8"
              value={state.createdFrom}
              onChange={(e) => setSingle("created_from", e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <FieldLabel>Created before</FieldLabel>
            <TextInput
              type="date"
              className="h-8"
              value={state.createdTo}
              onChange={(e) => setSingle("created_to", e.target.value)}
            />
          </label>

          <fieldset className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-6">
            <FieldLabel>Disposition</FieldLabel>
            <div className="flex flex-wrap gap-1">
              {DISPOSITIONS.map((d) => {
                const on = state.dispositions.includes(d);
                return (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={on}
                    onClick={() =>
                      setMulti(
                        "disposition",
                        on
                          ? state.dispositions.filter((x) => x !== d)
                          : [...state.dispositions, d],
                      )
                    }
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                      on
                        ? "border-primary bg-primary text-primary-fg"
                        : "border-border text-ink-tertiary hover:border-border-strong hover:text-ink",
                    )}
                  >
                    {d}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );
}
