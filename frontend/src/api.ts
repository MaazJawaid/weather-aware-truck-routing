import type { AnalyzeRequest, AnalyzeResponse } from "./types";

const base = import.meta.env.VITE_API_URL ?? "";

export async function analyzeTrip(body: AnalyzeRequest, signal: AbortSignal): Promise<AnalyzeResponse> {
  const response = await fetch(`${base}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  const data = (await response.json().catch(() => ({}))) as { detail?: string };
  if (!response.ok) {
    throw new Error(data.detail || "The trip could not be analyzed.");
  }
  return data as AnalyzeResponse;
}
