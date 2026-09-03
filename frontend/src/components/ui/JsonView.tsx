import { Fragment, type ReactNode } from "react";

const TOKEN =
  /("(?:\\.|[^"\\])*"\s*:)|("(?:\\.|[^"\\])*")|(\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(\btrue\b|\bfalse\b|\bnull\b)/g;

function highlightLine(line: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  TOKEN.lastIndex = 0;
  let i = 0;
  while ((m = TOKEN.exec(line))) {
    if (m.index > last) out.push(<Fragment key={i++}>{line.slice(last, m.index)}</Fragment>);
    const [tok, key, str, num, kw] = m;
    const cls = key
      ? "text-accent-subtle-fg"
      : str
        ? "text-diff-add-fg"
        : num
          ? "text-warning-subtle-fg"
          : kw
            ? "text-info-subtle-fg"
            : "";
    out.push(
      <span key={i++} className={cls}>
        {tok}
      </span>,
    );
    last = m.index + tok.length;
  }
  if (last < line.length) out.push(<Fragment key={i++}>{line.slice(last)}</Fragment>);
  return out;
}

export function JsonView({ value, maxHeight = "18rem" }: { value: unknown; maxHeight?: string }) {
  const text = JSON.stringify(value ?? {}, null, 2);
  const lines = text.split("\n");
  const empty = text === "{}" || text === "null";

  return (
    <div
      className="overflow-auto rounded-md border border-code-border bg-code-bg font-mono text-xs leading-relaxed text-code-fg"
      style={{ maxHeight }}
    >
      {empty ? (
        <p className="px-3 py-2 text-ink-tertiary">No payload recorded.</p>
      ) : (
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, n) => (
              <tr key={n}>
                <td className="select-none border-r border-border-subtle px-2 py-px text-right align-top text-ink-tertiary">
                  {n + 1}
                </td>
                <td className="whitespace-pre px-3 py-px align-top">{highlightLine(line)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
