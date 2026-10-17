import { Fragment, useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import { RISK_COLORS, RISK_LABELS } from "../colors";
import { formatMiles, formatWhen } from "../format";
import type { HeatPoint, RouteOption } from "../types";
import { HeatmapLayer } from "./HeatmapLayer";

function FitBounds({ routes }: { routes: RouteOption[] }) {
  const map = useMap();
  useEffect(() => {
    const bounds = L.latLngBounds([]);
    routes.forEach((route) => {
      route.geometry.forEach(([lat, lon]) => bounds.extend([lat, lon]));
    });
    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.15), { padding: [36, 36] });
    }
  }, [map, routes]);
  return null;
}

function SettleMap() {
  const map = useMap();
  useEffect(() => {
    const timer = window.setTimeout(() => map.invalidateSize(), 0);
    return () => window.clearTimeout(timer);
  }, [map]);
  return null;
}

function segmentPath(route: RouteOption, fromVertex: number, toVertex: number): [number, number][] {
  const slice = route.geometry.slice(fromVertex, toVertex + 1);
  return slice.length >= 2 ? slice : [];
}

interface MapViewProps {
  routes: RouteOption[];
  selectedId: string;
  heatPoints: HeatPoint[];
  hour: number;
}

export function MapView({ routes, selectedId, heatPoints, hour }: MapViewProps) {
  const renderer = useMemo(() => L.canvas({ padding: 0.5 }), []);
  const painted = [...routes].sort((left, right) => Number(left.id === selectedId) - Number(right.id === selectedId));

  return (
    <MapContainer center={[39.5, -96.5]} zoom={5} minZoom={3} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <SettleMap />
      {heatPoints.length > 0 ? <HeatmapLayer points={heatPoints} hour={hour} /> : null}
      {routes.length > 0 ? <FitBounds routes={routes} /> : null}
      {painted.map((route) => {
        const selected = route.id === selectedId;
        return (
          <Fragment key={route.id}>
            <Polyline
              positions={route.geometry}
              renderer={renderer}
              pathOptions={{ color: "#06110d", weight: selected ? 10 : 7, opacity: 0.55 }}
            />
            {route.segments.map((segment) => {
              const path = segmentPath(route, segment.from_vertex, segment.to_vertex);
              if (path.length < 2) return null;
              return (
                <Polyline
                  key={`${route.id}-${segment.from_vertex}-${segment.to_vertex}`}
                  positions={path}
                  renderer={renderer}
                  pathOptions={{
                    color: RISK_COLORS[segment.risk],
                    weight: selected ? 5 : 3,
                    opacity: selected ? 0.95 : 0.55,
                  }}
                />
              );
            })}
            {route.checkpoints.map((checkpoint) => (
              <CircleMarker
                key={`${route.id}-${checkpoint.mile}`}
                center={[checkpoint.lat, checkpoint.lon]}
                radius={selected ? 6 : 4}
                pathOptions={{
                  color: "#0c1411",
                  weight: 1,
                  fillColor: RISK_COLORS[checkpoint.risk],
                  fillOpacity: selected ? 1 : 0.75,
                }}
              >
                <Popup>
                  <div className="popup">
                    <strong>
                      {route.id.replace("_", " ")} · mile {checkpoint.mile}
                    </strong>
                    <p>ETA {formatWhen(checkpoint.eta)}</p>
                    <p>
                      {RISK_LABELS[checkpoint.risk]} · wind {checkpoint.wind_mph ?? "n/a"} mph · rain{" "}
                      {checkpoint.rain_in_hr ?? "n/a"} in/hr · snow {checkpoint.snow_in_hr ?? "n/a"} in/hr
                    </p>
                    <p>{formatMiles(checkpoint.mile)} along the route</p>
                    <ul>
                      {checkpoint.rules.map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </Fragment>
        );
      })}
    </MapContainer>
  );
}
