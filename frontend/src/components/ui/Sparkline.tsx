import { useId } from "react";
import { cn } from "./cn";

/** Tiny decorative trend line for stat cards. Deterministic from `seed`. */
export function Sparkline({
  seed = 0,
  tone = "accent",
  className,
}: {
  seed?: number;
  tone?: "accent" | "info" | "success" | "danger";
  className?: string;
}) {
  const id = useId();
  const w = 88;
  const h = 34;
  const n = 12;
  const raw: number[] = [];
  let v = 0.5;
  for (let i = 0; i < n; i++) {
    const t = Math.sin((i + seed) * 0.9) * 0.5 + Math.cos((i + seed) * 0.45) * 0.5;
    v = Math.min(0.9, Math.max(0.12, v + t * 0.1));
    raw.push(v);
  }
  // light 3-point smoothing so the line reads as a gentle trend
  const sm = raw.map((val, i) => (raw[i - 1] ?? val) * 0.25 + val * 0.5 + (raw[i + 1] ?? val) * 0.25);
  const pts: [number, number][] = sm.map((val, i) => [(i / (n - 1)) * w, h - val * (h - 4) - 2]);
  const line = pts
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${w} ${h} L0 ${h} Z`;
  const stroke = {
    accent: "var(--lime-500)",
    info: "var(--info)",
    success: "var(--success)",
    danger: "var(--danger)",
  }[tone];

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={cn("h-8 w-[5.5rem] overflow-visible", className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`sg-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${id})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[n - 1][0]} cy={pts[n - 1][1]} r="2.5" fill={stroke} />
    </svg>
  );
}
