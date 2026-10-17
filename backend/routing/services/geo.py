import math

EARTH_MILES = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(min(1.0, a)))


def cumulative_miles(coords: list[tuple[float, float]]) -> list[float]:
    totals = [0.0]
    for start, end in zip(coords, coords[1:]):
        totals.append(totals[-1] + haversine_miles(start[0], start[1], end[0], end[1]))
    return totals
