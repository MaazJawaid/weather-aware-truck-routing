export type RiskLevel = "low" | "moderate" | "high" | "severe" | "no_travel" | "unknown";

export interface Place {
  lat: number;
  lon: number;
  label: string;
}

export interface Checkpoint {
  lat: number;
  lon: number;
  mile: number;
  eta: string;
  vertex: number;
  wind_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  risk: RiskLevel;
  rules: string[];
}

export interface Segment {
  from_vertex: number;
  to_vertex: number;
  miles: number;
  risk: RiskLevel;
}

export interface RouteSummary {
  distance_mi: number;
  duration_seconds: number;
  duration_min: number;
  no_travel_miles: number;
  severe_miles: number;
  high_miles: number;
  moderate_miles: number;
  low_miles: number;
  unknown_miles: number;
  average_risk: number | null;
}

export interface RouteOption {
  id: string;
  rank: number;
  recommended: boolean;
  summary: RouteSummary;
  geometry: [number, number][];
  segments: Segment[];
  checkpoints: Checkpoint[];
}

export interface HeatPoint {
  lat: number;
  lon: number;
  risks: number[];
}

export interface AnalyzeResponse {
  recommended_route_id: string;
  no_fully_safe_route: boolean;
  reason: string;
  notice: string | null;
  departure: string;
  load_lb: number;
  sample_miles: number;
  origin: Place;
  destination: Place;
  routes: RouteOption[];
  heatmap: {
    generated_at: string;
    hours: string[];
    points: HeatPoint[];
  };
}

export interface AnalyzeRequest {
  origin: string;
  destination: string;
  departure: string;
  load_lb: number;
  sample_miles: 10 | 25 | 50;
}
