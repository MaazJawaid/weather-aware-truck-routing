import logging

import requests
from django.conf import settings

from routing.services.errors import TripError

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"


def parse_geocode_payload(payload: dict) -> dict | None:
    features = payload.get("features") or []
    if not features:
        return None
    feature = features[0]
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) < 2:
        return None
    lon, lat = coordinates[0], coordinates[1]
    label = str((feature.get("properties") or {}).get("label") or "")
    return {"lat": float(lat), "lon": float(lon), "label": label}


def geocode(text: str) -> dict:
    key = settings.OPENROUTESERVICE_API_KEY
    if not key:
        raise TripError("Add OPENROUTESERVICE_API_KEY to the .env file, then restart the server.", status=500)

    try:
        response = requests.get(
            GEOCODE_URL,
            params={"text": text, "size": 1},
            headers={"Authorization": key, "Accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.warning("geocode request failed: %s", exc)
        raise TripError("The geocoder could not be reached. Try again.", status=502) from exc

    if response.status_code in {401, 403}:
        raise TripError("The routing key was rejected.", status=502)
    if response.status_code == 429:
        raise TripError("The routing service is rate limited. Wait a moment and try again.", status=429)
    if response.status_code >= 400:
        raise TripError("The geocoder returned an error.", status=502)

    hit = parse_geocode_payload(response.json())
    if hit is None:
        raise TripError(f'No match for "{text}".')
    return hit
