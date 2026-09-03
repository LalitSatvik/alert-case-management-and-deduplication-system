import { Badge, type BadgeTone } from "./ui/Badge";

// Blue is reserved for affordances (selection, focus, primary action), never a
// status. Open is a neutral "new / untouched" tag; Closed is the quiet outline
// variant with no dot so the two read differently at a glance.
const CONFIG: Record<string, { tone: BadgeTone; variant: "soft" | "outline"; dot: boolean }> = {
  Open: { tone: "neutral", variant: "soft", dot: true },
  "In Progress": { tone: "warning", variant: "soft", dot: true },
  "Pending Info": { tone: "info", variant: "soft", dot: true },
  Closed: { tone: "neutral", variant: "outline", dot: false },
  Merged: { tone: "success", variant: "soft", dot: true },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = CONFIG[status] ?? { tone: "neutral" as const, variant: "outline" as const, dot: false };
  return (
    <Badge tone={cfg.tone} variant={cfg.variant} dot={cfg.dot} uppercase>
      {status}
    </Badge>
  );
}
