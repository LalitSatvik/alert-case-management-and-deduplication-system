type Tone = "accent" | "warning" | "info" | "neutral" | "success";

const TONE: Record<string, Tone> = {
  Open: "accent",
  "In Progress": "warning",
  "Pending Info": "info",
  Closed: "neutral",
  Merged: "success",
};

const TONE_CLASS: Record<Tone, string> = {
  accent: "bg-accent-subtle text-accent-subtle-fg ring-accent-border",
  warning: "bg-warning-subtle text-warning-subtle-fg ring-warning-border",
  info: "bg-info-subtle text-info-subtle-fg ring-info-border",
  neutral: "bg-neutral-subtle text-neutral-subtle-fg ring-neutral-border",
  success: "bg-success-subtle text-success-subtle-fg ring-success-border",
};

const DOT_CLASS: Record<Tone, string> = {
  accent: "bg-accent",
  warning: "bg-warning",
  info: "bg-info",
  neutral: "bg-ink-muted",
  success: "bg-success",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONE[status] ?? "neutral";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset transition-colors duration-3 ${TONE_CLASS[tone]}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-3 ${DOT_CLASS[tone]}`}
      />
      {status}
    </span>
  );
}
