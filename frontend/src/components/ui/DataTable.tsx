import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Checkbox } from "./Checkbox";
import { cn } from "./cn";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Right-align for numeric columns. */
  align?: "left" | "right";
  /** When set, the header becomes a sort control that calls `onSort(sortKey)`. */
  sortKey?: string;
  /** Extra classes on the `<td>` (and `<th>`). */
  className?: string;
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Whole-row navigation target. Row click / Enter goes here. */
  rowHref?: (row: T) => string;
  /** Left accent bar colour class per row, e.g. a risk band. */
  rowAccent?: (row: T) => string | undefined;

  selectable?: boolean;
  selected?: Set<string>;
  onToggleRow?: (key: string) => void;
  onToggleAll?: () => void;

  /** Current sort value; a column whose `sortKey` matches shows the caret. */
  sort?: string;
  onSort?: (sortKey: string) => void;

  empty?: ReactNode;
  /** px height of any sticky toolbar above the table, so the header sticks below it. */
  headerTop?: number;
}

function Caret({ dir }: { dir: "asc" | "desc" | null }) {
  return (
    <span aria-hidden="true" className="ml-1 inline-block w-2 text-ink">
      {dir === "asc" ? "▲" : dir === "desc" ? "▼" : ""}
    </span>
  );
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowHref,
  rowAccent,
  selectable = false,
  selected,
  onToggleRow,
  onToggleAll,
  sort,
  onSort,
  empty,
  headerTop = 0,
}: DataTableProps<T>) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(-1);

  const keys = useMemo(() => rows.map(rowKey), [rows, rowKey]);
  const allSelected = selectable && rows.length > 0 && keys.every((k) => selected?.has(k));

  // keep the active row in range as the data changes
  useEffect(() => {
    if (activeIdx >= rows.length) setActiveIdx(rows.length - 1);
  }, [rows.length, activeIdx]);

  function activate(idx: number) {
    const row = rows[idx];
    if (row && rowHref) navigate(rowHref(row));
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

    if (e.key === "j" || e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(rows.length - 1, i + 1));
    } else if (e.key === "k" || e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i < 0 ? 0 : i - 1));
    } else if (e.key === "Enter") {
      if (activeIdx >= 0) {
        e.preventDefault();
        activate(activeIdx);
      }
    } else if ((e.key === "x" || e.key === " ") && selectable && activeIdx >= 0) {
      e.preventDefault();
      onToggleRow?.(keys[activeIdx]);
    }
  }

  useEffect(() => {
    if (activeIdx < 0) return;
    const el = containerRef.current?.querySelector<HTMLElement>(`[data-row-idx="${activeIdx}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  const gridCols = columns.length + (selectable ? 1 : 0);

  return (
    <div
      ref={containerRef}
      role="grid"
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="overflow-auto rounded-md border border-border bg-surface focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-focus"
    >
      <table className="min-w-full border-separate border-spacing-0 text-table">
        <thead>
          <tr>
            {selectable && (
              <th
                style={{ top: headerTop }}
                className="sticky z-10 w-8 border-b border-border bg-surface-sunken px-cell-x py-cell-y"
              >
                <Checkbox
                  aria-label="Select all rows"
                  checked={allSelected}
                  onCheckedChange={() => onToggleAll?.()}
                />
              </th>
            )}
            {columns.map((c) => {
              const active = c.sortKey && sort === c.sortKey;
              return (
                <th
                  key={c.key}
                  style={{ top: headerTop, width: c.width }}
                  className={cn(
                    "sticky z-10 border-b border-border bg-surface-sunken px-cell-x py-cell-y text-2xs font-semibold uppercase tracking-wider text-ink-tertiary",
                    c.align === "right" ? "text-right" : "text-left",
                    c.className,
                  )}
                >
                  {c.sortKey && onSort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.sortKey!)}
                      className={cn(
                        "inline-flex items-center uppercase tracking-wider transition-colors hover:text-ink",
                        active && "text-ink",
                      )}
                    >
                      {c.header}
                      <Caret dir={active ? "desc" : null} />
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const key = keys[idx];
            const isSelected = selected?.has(key) ?? false;
            const isActive = idx === activeIdx;
            const accent = rowAccent?.(row);
            return (
              <tr
                key={key}
                data-row-idx={idx}
                aria-selected={isSelected}
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest("input,button,a")) return;
                  setActiveIdx(idx);
                  if (rowHref) navigate(rowHref(row));
                }}
                className={cn(
                  "group",
                  rowHref && "cursor-pointer",
                  isSelected && "bg-accent-subtle",
                  isActive && !isSelected && "bg-surface-hover",
                  !isActive && !isSelected && "hover:bg-surface-hover",
                )}
              >
                {selectable && (
                  <td className="relative border-b border-border-subtle px-cell-x py-cell-y align-middle">
                    {accent && (
                      <span
                        aria-hidden="true"
                        className={cn("absolute inset-y-0 left-0 w-[3px]", accent)}
                      />
                    )}
                    <Checkbox
                      aria-label="Select row"
                      checked={isSelected}
                      onCheckedChange={() => onToggleRow?.(key)}
                    />
                  </td>
                )}
                {columns.map((c, ci) => (
                  <td
                    key={c.key}
                    className={cn(
                      "relative border-b border-border-subtle px-cell-x py-cell-y align-middle leading-tight text-ink-secondary group-hover:text-ink",
                      c.align === "right" && "text-right tabular-nums",
                      c.className,
                    )}
                  >
                    {!selectable && ci === 0 && accent && (
                      <span
                        aria-hidden="true"
                        className={cn("absolute inset-y-0 left-0 w-[3px]", accent)}
                      />
                    )}
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={gridCols} className="px-cell-x py-10 text-center text-sm text-ink-tertiary">
                {empty ?? "No results."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
