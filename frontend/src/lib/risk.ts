export type RiskBand = "low" | "elev" | "high" | "sev" | "crit";

/** Score → band. Boundaries: low 0-39 / elevated 40-59 / high 60-79 / severe 80-89 / critical 90-100. */
export function riskBand(score: number): RiskBand {
  if (score >= 90) return "crit";
  if (score >= 80) return "sev";
  if (score >= 60) return "high";
  if (score >= 40) return "elev";
  return "low";
}

export const RISK_BAND_LABEL: Record<RiskBand, string> = {
  low: "Low",
  elev: "Elevated",
  high: "High",
  sev: "Severe",
  crit: "Critical",
};
