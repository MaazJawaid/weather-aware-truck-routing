import type { AnalyzeRequest } from "../types";

const PRESETS: { label: string; origin: string; destination: string }[] = [
  { label: "Chicago to Detroit", origin: "Chicago, IL", destination: "Detroit, MI" },
  { label: "Denver to Kansas City", origin: "Denver, CO", destination: "Kansas City, MO" },
];

interface TripFormProps {
  origin: string;
  destination: string;
  departure: string;
  loadLb: string;
  sampleMiles: 10 | 25 | 50;
  loading: boolean;
  onOrigin: (value: string) => void;
  onDestination: (value: string) => void;
  onDeparture: (value: string) => void;
  onLoad: (value: string) => void;
  onSample: (value: 10 | 25 | 50) => void;
  onSubmit: (body: AnalyzeRequest) => void;
}

export function TripForm({
  origin,
  destination,
  departure,
  loadLb,
  sampleMiles,
  loading,
  onOrigin,
  onDestination,
  onDeparture,
  onLoad,
  onSample,
  onSubmit,
}: TripFormProps) {
  return (
    <form
      className="trip-form"
      onSubmit={(event) => {
        event.preventDefault();
        const load = Number(loadLb);
        if (!origin.trim() || !destination.trim()) return;
        if (!Number.isFinite(load) || load <= 0) return;
        onSubmit({
          origin: origin.trim(),
          destination: destination.trim(),
          departure,
          load_lb: load,
          sample_miles: sampleMiles,
        });
      }}
    >
      <div className="presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="preset"
            onClick={() => {
              onOrigin(preset.origin);
              onDestination(preset.destination);
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <label>
        Origin
        <input value={origin} onChange={(event) => onOrigin(event.target.value)} placeholder="City, state" required />
      </label>
      <label>
        Destination
        <input
          value={destination}
          onChange={(event) => onDestination(event.target.value)}
          placeholder="City, state"
          required
        />
      </label>
      <label>
        Departure
        <input type="datetime-local" value={departure} onChange={(event) => onDeparture(event.target.value)} required />
      </label>
      <label>
        Load weight (lb)
        <input
          type="number"
          min={1}
          max={200000}
          step={1}
          value={loadLb}
          onChange={(event) => onLoad(event.target.value)}
          required
        />
      </label>
      <p className="hint">
        Over 30,000 lb, 45–54 mph wind is no-travel. Over 40,000 lb, 35–44 mph wind becomes severe.
      </p>

      <fieldset>
        <legend>Checkpoint spacing</legend>
        <div className="spacing">
          {(
            [
              [10, "10 mi", "More detail"],
              [25, "25 mi", "Default"],
              [50, "50 mi", "Faster"],
            ] as const
          ).map(([miles, label, note]) => (
            <label key={miles} className={sampleMiles === miles ? "spacing-on" : ""}>
              <input
                type="radio"
                name="spacing"
                checked={sampleMiles === miles}
                onChange={() => onSample(miles)}
              />
              <span>{label}</span>
              <small>{note}</small>
            </label>
          ))}
        </div>
      </fieldset>

      <button type="submit" className="submit" disabled={loading}>
        {loading ? "Scoring routes…" : "Score routes"}
      </button>
    </form>
  );
}
