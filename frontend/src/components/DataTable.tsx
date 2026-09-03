import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /**
   * When true, rows get a hover affordance. Navigation itself is the caller's
   * responsibility — put a real `<Link>` in the first column's `render` (give it
   * `class="after:absolute after:inset-0"` to make the whole row its hit area).
   * No `role="button"` on the row, so cells keep their table semantics.
   */
  interactive?: boolean;
  empty?: ReactNode;
}

export function DataTable<T>({ columns, rows, rowKey, interactive, empty }: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface shadow-xs">
      <table className="min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`sticky top-0 z-10 border-b border-border bg-surface-sunken px-3.5 py-2.5 text-left text-2xs font-semibold uppercase tracking-wider text-ink-tertiary ${c.className ?? ""}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="u-stagger">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={
                interactive
                  ? "group relative transition-colors duration-2 hover:bg-surface-hover hover:[box-shadow:inset_2px_0_0_var(--accent)] focus-within:bg-surface-hover"
                  : undefined
              }
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`border-b border-border-subtle px-3.5 py-2.5 text-ink-secondary group-hover:text-ink ${c.className ?? ""}`}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3.5 py-10 text-center text-sm text-ink-tertiary"
              >
                {empty ?? "No results."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
