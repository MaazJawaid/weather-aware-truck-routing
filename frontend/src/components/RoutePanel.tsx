import { formatDuration, formatMiles } from "../format";
import type { AnalyzeResponse, RouteOption } from "../types";

interface RoutePanelProps {
  result: AnalyzeResponse;
  selectedId: string;
  onSelect: (id: string) => void;
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function Card({ route, selected, onSelect }: { route: RouteOption; selected: boolean; onSelect: () => void }) {
  const summary = route.summary;
  return (
    <button type="button" className={selected ? "route-card selected" : "route-card"} onClick={onSelect}>
      <header>
        <span>Option {route.id.replace("route_", "")}</span>
        {route.recommended ? <em>Recommended</em> : <small>Rank {route.rank}</small>}
      </header>
      <div className="stat-grid">
        <Stat label="Distance" value={formatMiles(summary.distance_mi)} />
        <Stat label="Time" value={formatDuration(summary.duration_seconds)} />
        <Stat label="No travel" value={formatMiles(summary.no_travel_miles)} tone="tone-closed" />
        <Stat label="Severe" value={formatMiles(summary.severe_miles)} tone="tone-severe" />
        <Stat label="High" value={formatMiles(summary.high_miles)} tone="tone-high" />
        <Stat
          label="Avg risk"
          value={summary.average_risk == null ? "n/a" : summary.average_risk.toFixed(2)}
        />
      </div>
      <p className="card-meta">
        {route.checkpoints.length} checkpoints
        {summary.unknown_miles > 0 ? ` · ${formatMiles(summary.unknown_miles)} unknown` : ""}
      </p>
    </button>
  );
}

export function RoutePanel({ result, selectedId, onSelect }: RoutePanelProps) {
  return (
    <section className="results">
      <div className="results-head">
        <h2>
          {result.origin.label || "Origin"}
          <span>to</span>
          {result.destination.label || "Destination"}
        </h2>
        <p>{result.reason}</p>
      </div>
      {result.no_fully_safe_route ? (
        <p className="banner danger">No fully safe route. Every option has no-travel miles.</p>
      ) : null}
      {result.notice ? <p className="banner">{result.notice}</p> : null}
      {result.routes.map((route) => (
        <Card key={route.id} route={route} selected={route.id === selectedId} onSelect={() => onSelect(route.id)} />
      ))}
    </section>
  );
}
