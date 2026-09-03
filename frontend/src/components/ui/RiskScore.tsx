import { riskBand, RISK_BAND_LABEL, RISK_BAR_BG, type RiskBand } from "../../lib/risk";
import { cn } from "./cn";

type Size = "sm" | "md";

const BAR = RISK_BAR_BG;
const FG: Record<RiskBand, string> = {
  low: "text-risk-low-fg",
  elev: "text-risk-elev-fg",
  high: "text-risk-high-fg",
  sev: "text-risk-sev-fg",
  crit: "text-risk-crit-fg",
};
const CHIP_BG: Record<RiskBand, string> = {
  low: "bg-risk-low-bg",
  elev: "bg-risk-elev-bg",
  high: "bg-risk-high-bg",
  sev: "bg-risk-sev-bg",
  crit: "bg-risk-crit-bg",
};

export function RiskScore({
  score,
  size = "sm",
  className,
}: {
  score: number;
  size?: Size;
  className?: string;
}) {
  const band = riskBand(score);
  const label = RISK_BAND_LABEL[band];

  if (size === "md") {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-2.5 rounded-full px-3 py-1.5",
          CHIP_BG[band],
          className,
        )}
      >
        <span className={cn("text-xl font-semibold tabular-nums leading-none", FG[band])}>{score}</span>
        <span className={cn("text-xs font-semibold", FG[band])}>{label}</span>
      </div>
    );
  }

  return (
    <span
      className={cn("inline-flex items-center gap-2 tabular-nums leading-none", className)}
      title={`${label} risk`}
    >
      <span aria-hidden="true" className={cn("h-3.5 w-1 shrink-0 rounded-full", BAR[band])} />
      <span className={cn("text-sm font-semibold", FG[band])}>{score}</span>
    </span>
  );
}
