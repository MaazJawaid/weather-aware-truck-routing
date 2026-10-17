"""A coarse grid of points inside a buffer around the trip, for the heatmap."""

from __future__ import annotations

import math

from routing.services.geo import haversine_miles
from routing.services.sampling import resample_line

BUFFER_MILES = 25
SPACING_MILES = 16
MAX_POINTS = 250


def _nearby(lat: float, lon: float, samples: list[tuple[float, float]], buffer_miles: float) -> bool:
    for sample_lat, sample_lon in samples:
        if haversine_miles(lat, lon, sample_lat, sample_lon) <= buffer_miles:
            return True
    return False


def build_corridor(
    lines: list[list[tuple[float, float]]],
    buffer_miles: float = BUFFER_MILES,
    spacing_miles: float = SPACING_MILES,
    max_points: int = MAX_POINTS,
) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    for line in lines:
        samples.extend(resample_line(line, 5))
    if not samples:
        return []

    latitudes = [point[0] for point in samples]
    longitudes = [point[1] for point in samples]
    mid_lat = sum(latitudes) / len(latitudes)
    lat_pad = buffer_miles / 69.0
    lon_miles = max(10.0, 69.0 * math.cos(math.radians(mid_lat)))
    lon_pad = buffer_miles / lon_miles

    min_lat = min(latitudes) - lat_pad
    max_lat = max(latitudes) + lat_pad
    min_lon = min(longitudes) - lon_pad
    max_lon = max(longitudes) + lon_pad
    lat_step = spacing_miles / 69.0
    lon_step = spacing_miles / lon_miles

    points: list[tuple[float, float]] = []
    lat = min_lat
    while lat <= max_lat + 1e-9:
        lon = min_lon
        while lon <= max_lon + 1e-9:
            rounded = (round(lat, 2), round(lon, 2))
            if _nearby(rounded[0], rounded[1], samples, buffer_miles):
                points.append(rounded)
            lon += lon_step
        lat += lat_step

    unique = list(dict.fromkeys(points))
    if len(unique) > max_points:
        stride = math.ceil(len(unique) / max_points)
        unique = unique[::stride]
    return unique
