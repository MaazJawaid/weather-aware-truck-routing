"""Tie geocoding, truck routes, sampling, weather, and ranking into one payload."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from routing.services.corridor import build_corridor
from routing.services.directions import fetch_routes
from routing.services.errors import TripError
from routing.services.geocoding import geocode
from routing.services.geo import haversine_miles
from routing.services.recommend import build_segments, explain_ranking, rank_routes, summarize_segments
from routing.services.risk import RISK_CODE, classify
from routing.services.sampling import sample_route, simplify_line
from routing.services.weather import fetch_forecasts, floor_hour, forecast_window


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _iso(moment: datetime) -> str:
    return _as_utc(moment).isoformat().replace("+00:00", "Z")


def _same_place(origin: dict, destination: dict) -> bool:
    return haversine_miles(origin["lat"], origin["lon"], destination["lat"], destination["lon"]) < 0.4


def _score_checkpoints(samples, forecasts, departure, load_lb) -> list[dict]:
    checkpoints = []
    for point in samples:
        key = (round(point.lat, 2), round(point.lon, 2))
        indexed = {hour.time: hour for hour in forecasts.get(key, [])}
        eta = departure + timedelta(seconds=point.eta_offset_seconds)
        hour = indexed.get(floor_hour(eta))
        if hour is None:
            weather = classify(None, None, None, load_lb)
        else:
            weather = classify(hour.wind_mph, hour.rain_in_hr, hour.snow_in_hr, load_lb)
        checkpoints.append(
            {
                "lat": round(point.lat, 5),
                "lon": round(point.lon, 5),
                "mile": point.mile,
                "eta": _iso(eta),
                "vertex": point.vertex,
                "wind_mph": weather["wind_mph"],
                "rain_in_hr": weather["rain_in_hr"],
                "snow_in_hr": weather["snow_in_hr"],
                "risk": weather["risk"],
                "rules": weather["rules"],
            }
        )
    return checkpoints


def _present_geometry(coords, checkpoints, segments) -> tuple[list, list, list]:
    keep = {int(point["vertex"]) for point in checkpoints}
    simplified, mapping = simplify_line(coords, keep)
    geometry = [[round(lat, 5), round(lon, 5)] for lat, lon in simplified]
    for point in checkpoints:
        point["vertex"] = mapping[int(point["vertex"])]
    for segment in segments:
        segment["from_vertex"] = mapping[int(segment["from_vertex"])]
        segment["to_vertex"] = mapping[int(segment["to_vertex"])]
        if segment["to_vertex"] < segment["from_vertex"]:
            segment["from_vertex"], segment["to_vertex"] = segment["to_vertex"], segment["from_vertex"]
    return geometry, checkpoints, segments


def _heatmap(points, forecasts, load_lb, now) -> dict:
    hours = forecast_window(now, 49)
    encoded = []
    for lat, lon in points:
        indexed = {hour.time: hour for hour in forecasts.get((lat, lon), [])}
        risks = []
        for moment in hours:
            hour = indexed.get(moment)
            if hour is None:
                risks.append(0)
            else:
                level = classify(hour.wind_mph, hour.rain_in_hr, hour.snow_in_hr, load_lb)["risk"]
                risks.append(RISK_CODE[level])
        encoded.append({"lat": lat, "lon": lon, "risks": risks})
    return {
        "generated_at": _iso(now),
        "hours": [_iso(moment) for moment in hours],
        "points": encoded,
    }


def analyze_trip(
    *,
    origin: str,
    destination: str,
    departure: datetime,
    load_lb: float,
    sample_miles: int,
    now: datetime | None = None,
) -> dict:
    departure = _as_utc(departure)
    now = _as_utc(now or datetime.now(timezone.utc))

    origin_hit = geocode(origin.strip())
    destination_hit = geocode(destination.strip())
    if _same_place(origin_hit, destination_hit):
        raise TripError("Origin and destination resolve to the same place.")

    routes = fetch_routes(origin_hit, destination_hit, load_lb)
    if not routes:
        raise TripError("No drivable truck route was found for that pair.", status=422)

    needed: list[tuple[float, float]] = []
    drafted = []
    for index, route in enumerate(routes[:3], start=1):
        samples = sample_route(
            route["coords"],
            route["distance_mi"],
            route["duration_seconds"],
            sample_miles,
            route["steps"],
        )
        drafted.append({"id": f"route_{index}", "route": route, "samples": samples})
        needed.extend((point.lat, point.lon) for point in samples)

    corridor = build_corridor([item["route"]["coords"] for item in drafted])
    needed.extend(corridor)
    forecasts = fetch_forecasts(needed)

    scored = []
    for item in drafted:
        checkpoints = _score_checkpoints(item["samples"], forecasts, departure, load_lb)
        segments = build_segments(checkpoints)
        geometry, checkpoints, segments = _present_geometry(item["route"]["coords"], checkpoints, segments)
        scored.append(
            {
                "id": item["id"],
                "summary": summarize_segments(
                    segments,
                    item["route"]["distance_mi"],
                    item["route"]["duration_seconds"],
                ),
                "geometry": geometry,
                "segments": segments,
                "checkpoints": checkpoints,
            }
        )

    ordered = rank_routes(scored)
    winner = ordered[0]
    for rank, route in enumerate(ordered, start=1):
        route["rank"] = rank
        route["recommended"] = route["id"] == winner["id"]

    count = len(ordered)
    notice = None
    if count < 3:
        noun = "route" if count == 1 else "routes"
        notice = f"The road network returned {count} {noun} for this trip."

    return {
        "recommended_route_id": winner["id"],
        "no_fully_safe_route": all(route["summary"]["no_travel_miles"] > 0 for route in ordered),
        "reason": explain_ranking(winner),
        "notice": notice,
        "departure": _iso(departure),
        "load_lb": load_lb,
        "sample_miles": sample_miles,
        "origin": origin_hit,
        "destination": destination_hit,
        "routes": ordered,
        "heatmap": _heatmap(corridor, forecasts, load_lb, now),
    }
