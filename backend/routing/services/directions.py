import logging

import requests
from django.conf import settings

from routing.services.errors import TripError
from routing.services.geo import haversine_miles

logger = logging.getLogger(__name__)

DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
LB_PER_TONNE = 2204.6226218
# The public alternative-route algorithm rejects trips beyond 100 km.
# Stay under that limit; the check uses straight-line distance.
ALTERNATIVE_MAX_METERS = 90_000
METERS_PER_MILE = 1609.344


def tonnes_from_pounds(load_lb: float) -> float:
    return round(max(0.1, load_lb / LB_PER_TONNE), 2)


def parse_directions_payload(payload: dict) -> list[dict]:
    routes = []
    for feature in payload.get("features") or []:
        raw = (feature.get("geometry") or {}).get("coordinates") or []
        coords = [(float(point[1]), float(point[0])) for point in raw if len(point) >= 2]
        if len(coords) < 2:
            continue
        properties = feature.get("properties") or {}
        summary = properties.get("summary") or {}
        distance = float(summary.get("distance") or 0)
        duration = float(summary.get("duration") or 0)
        if distance <= 0:
            continue
        steps = []
        for segment in properties.get("segments") or []:
            for step in segment.get("steps") or []:
                steps.append(
                    {
                        "distance": float(step.get("distance") or 0),
                        "duration": float(step.get("duration") or 0),
                    }
                )
        routes.append(
            {
                "distance_mi": distance,
                "duration_seconds": duration,
                "coords": coords,
                "steps": steps,
            }
        )
    return routes[:3]


def _error_text(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "")[:180]
    if isinstance(error, str):
        return error[:180]
    return ""


def route_request_body(
    origin: dict,
    destination: dict,
    load_lb: float,
    *,
    alternatives: bool,
    preference: str | None = None,
) -> dict:
    body = {
        "coordinates": [
            [origin["lon"], origin["lat"]],
            [destination["lon"], destination["lat"]],
        ],
        "options": {
            "profile_params": {
                "restrictions": {
                    "weight": tonnes_from_pounds(load_lb),
                }
            }
        },
        "units": "mi",
    }
    if alternatives:
        # target_count is the number of alternatives besides the primary route.
        body["alternative_routes"] = {
            "target_count": 2,
            "share_factor": 0.6,
            "weight_factor": 1.4,
        }
    if preference:
        body["preference"] = preference
    return body


def within_alternative_limit(origin: dict, destination: dict) -> bool:
    miles = haversine_miles(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    return miles * METERS_PER_MILE <= ALTERNATIVE_MAX_METERS


def alternative_limit_error(message: str) -> bool:
    text = message.lower()
    return "alternative" in text and ("100000" in text or "configuration limit" in text)


def _sampled(coords: list[tuple[float, float]], count: int = 7) -> list[tuple[float, float]]:
    if not coords:
        return []
    if len(coords) == 1:
        return coords * count
    last = len(coords) - 1
    return [coords[round(index * last / (count - 1))] for index in range(count)]


def same_corridor(left: dict, right: dict, threshold_mi: float = 5.0) -> bool:
    """True when two lines stay on essentially the same roads."""
    left_points = _sampled(left["coords"])
    right_points = _sampled(right["coords"])
    if not left_points or not right_points:
        return False
    gaps = [
        haversine_miles(a_lat, a_lon, b_lat, b_lon)
        for (a_lat, a_lon), (b_lat, b_lon) in zip(left_points, right_points)
    ]
    return (sum(gaps) / len(gaps)) < threshold_mi


def merge_routes(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = list(existing)
    for route in incoming:
        if any(same_corridor(route, kept) for kept in merged):
            continue
        merged.append(route)
        if len(merged) >= 3:
            break
    return merged


def _post_routes(key: str, body: dict) -> list[dict]:
    try:
        response = requests.post(
            DIRECTIONS_URL,
            json=body,
            headers={
                "Authorization": key,
                "Accept": "application/json, application/geo+json",
                "Content-Type": "application/json",
            },
            timeout=40,
        )
    except requests.RequestException as exc:
        logger.warning("directions request failed: %s", exc)
        raise TripError("The routing service could not be reached. Try again.", status=502) from exc

    if response.status_code in {401, 403}:
        raise TripError("The routing key was rejected.", status=502)
    if response.status_code == 429:
        raise TripError("The routing service is rate limited. Wait a moment and try again.", status=429)
    if response.status_code == 404:
        raise TripError("No drivable truck route was found for that pair.", status=422)
    if response.status_code >= 400:
        detail = _error_text(response)
        message = "The routing service rejected this trip."
        if detail:
            message = f"{message} {detail}"
        raise TripError(message, status=422)

    return parse_directions_payload(response.json())


def fetch_routes(origin: dict, destination: dict, load_lb: float) -> list[dict]:
    key = settings.OPENROUTESERVICE_API_KEY
    if not key:
        raise TripError("Add OPENROUTESERVICE_API_KEY to the .env file, then restart the server.", status=500)

    alternatives = within_alternative_limit(origin, destination)
    try:
        routes = _post_routes(key, route_request_body(origin, destination, load_lb, alternatives=alternatives))
    except TripError as exc:
        if not (alternatives and alternative_limit_error(str(exc))):
            raise
        logger.info("alternative routes are unavailable at this distance; requesting the direct route")
        routes = _post_routes(key, route_request_body(origin, destination, load_lb, alternatives=False))

    for preference in ("fastest", "shortest"):
        if len(routes) >= 3:
            break
        try:
            extra = _post_routes(
                key,
                route_request_body(origin, destination, load_lb, alternatives=False, preference=preference),
            )
        except TripError as exc:
            logger.info("skipped %s route: %s", preference, exc)
            continue
        routes = merge_routes(routes, extra)

    return routes[:3]
