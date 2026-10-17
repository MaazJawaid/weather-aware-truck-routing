import type { RiskLevel } from "./types";

export const RISK_COLORS: Record<RiskLevel, string> = {
  low: "#2f9e62",
  moderate: "#d4a017",
  high: "#e07a1f",
  severe: "#d64545",
  no_travel: "#7a3ea1",
  unknown: "#8b97a6",
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No travel",
  unknown: "Unknown",
};

export const RISK_LEVELS: RiskLevel[] = ["low", "moderate", "high", "severe", "no_travel", "unknown"];

export const HEAT_RGB: Record<number, string> = {
  0: "139, 151, 166",
  1: "47, 158, 98",
  2: "212, 160, 23",
  3: "224, 122, 31",
  4: "214, 69, 69",
  5: "122, 62, 161",
};
