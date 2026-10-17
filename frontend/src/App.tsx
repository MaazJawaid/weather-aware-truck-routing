import { useRef, useState } from "react";
import { analyzeTrip } from "./api";
import { Legend } from "./components/Legend";
import { ForecastSlider } from "./components/ForecastSlider";
import { MapView } from "./components/MapView";
import { RoutePanel } from "./components/RoutePanel";
import { TripForm } from "./components/TripForm";
import { defaultDeparture, localInputToIso } from "./format";
import type { AnalyzeRequest, AnalyzeResponse } from "./types";

export function App() {
  const [origin, setOrigin] = useState("Chicago, IL");
  const [destination, setDestination] = useState("Detroit, MI");
  const [departure, setDeparture] = useState(defaultDeparture);
  const [loadLb, setLoadLb] = useState("35000");
  const [sampleMiles, setSampleMiles] = useState<10 | 25 | 50>(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [hour, setHour] = useState(0);
  const request = useRef<AbortController | null>(null);

  async function submit(body: AnalyzeRequest) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    try {
      const payload = await analyzeTrip(
        { ...body, departure: localInputToIso(body.departure) },
        controller.signal,
      );
      setResult(payload);
      setSelectedId(payload.recommended_route_id);
      setHour(0);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(caught instanceof Error ? caught.message : "The trip could not be analyzed.");
    } finally {
      if (request.current === controller) setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="panel">
        <header className="brand">
          <span className="mark" aria-hidden="true">
            WR
          </span>
          <div>
            <p>Route desk</p>
            <h1>Weather-aware truck routing</h1>
          </div>
        </header>
        <TripForm
          origin={origin}
          destination={destination}
          departure={departure}
          loadLb={loadLb}
          sampleMiles={sampleMiles}
          loading={loading}
          onOrigin={setOrigin}
          onDestination={setDestination}
          onDeparture={setDeparture}
          onLoad={setLoadLb}
          onSample={setSampleMiles}
          onSubmit={(body) => {
            void submit(body);
          }}
        />
        {error ? (
          <div className="callout" role="alert">
            <strong>Can’t score this trip</strong>
            <p>{error}</p>
          </div>
        ) : null}
        {result ? <RoutePanel result={result} selectedId={selectedId} onSelect={setSelectedId} /> : null}
      </aside>
      <main className="stage">
        <section className="map-frame">
        <MapView
          routes={result?.routes ?? []}
          selectedId={selectedId}
          heatPoints={result?.heatmap.points ?? []}
          hour={hour}
        />
        <div className="dock">
          <Legend />
          {result ? (
            <ForecastSlider
              hour={hour}
              hours={result.heatmap.hours}
              departure={result.departure}
              onChange={setHour}
            />
          ) : (
            <p className="empty-map">Score a trip to compare three truck routes against the forecast.</p>
          )}
        </div>
        {loading ? <p className="loading">Checking roads and the forecast</p> : null}
        </section>
      </main>
    </div>
  );
}
