import { Badge, type BadgeTone } from "./ui/Badge";

const CONFIG: Record<string, { tone: BadgeTone; dot: boolean }> = {
  Open: { tone: "info", dot: true },
  "In Progress": { tone: "warning", dot: true },
  "Pending Info": { tone: "neutral", dot: true },
  Closed: { tone: "success", dot: false },
  Merged: { tone: "accent", dot: false },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = CONFIG[status] ?? { tone: "neutral" as const, dot: false };
  return (
    <Badge tone={cfg.tone} dot={cfg.dot}>
      {status}
    </Badge>
  );
}
