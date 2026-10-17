"""Place checkpoints every N road miles and attach an ETA from the route profile."""

from __future__ import annotations

from dataclasses import dataclass

from routing.services.geo import cumulative_miles, haversine_miles


@dataclass(frozen=True)
class SamplePoint:
    lat: float
    lon: float
    mile: float
    eta_offset_seconds: float
    vertex: int


def _mile_duration_table(
    steps: list[dict] | None,
    distance_mi: float,
    duration_seconds: float,
) -> list[tuple[float, float]]:
    if not steps:
        return [(0.0, 0.0), (distance_mi, duration_seconds)]

    mile = 0.0
    seconds = 0.0
    table = [(0.0, 0.0)]
    for step in steps:
        mile += max(0.0, float(step.get("distance") or 0))
        seconds += max(0.0, float(step.get("duration") or 0))
        table.append((mile, seconds))

    end_mile, end_seconds = table[-1]
    if end_mile > 0 and distance_mi > 0 and abs(end_mile - distance_mi) > 0.05:
        mile_scale = distance_mi / end_mile
        time_scale = (duration_seconds / end_seconds) if end_seconds else 1.0
        table = [(item_mile * mile_scale, item_seconds * time_scale) for item_mile, item_seconds in table]
    elif end_mile == 0:
        return [(0.0, 0.0), (distance_mi, duration_seconds)]
    return table


def duration_at_mile(table: list[tuple[float, float]], mile: float) -> float:
    if not table or mile <= table[0][0]:
        return table[0][1] if table else 0.0
    for (mile_0, time_0), (mile_1, time_1) in zip(table, table[1:]):
        if mile <= mile_1:
            span = mile_1 - mile_0
            if span <= 0:
                return time_1
            fraction = (mile - mile_0) / span
            return time_0 + (time_1 - time_0) * fraction
    return table[-1][1]


def _point_at_fraction(
    coords: list[tuple[float, float]],
    cumulative: list[float],
    fraction: float,
) -> tuple[tuple[float, float], int]:
    if len(coords) == 1 or fraction <= 0:
        return coords[0], 0
    if fraction >= 1:
        return coords[-1], len(coords) - 1

    target = cumulative[-1] * fraction
    for index in range(1, len(coords)):
        if cumulative[index] + 1e-9 >= target:
            span = cumulative[index] - cumulative[index - 1]
            local = 0.0 if span <= 0 else (target - cumulative[index - 1]) / span
            local = min(1.0, max(0.0, local))
            lat = coords[index - 1][0] + (coords[index][0] - coords[index - 1][0]) * local
            lon = coords[index - 1][1] + (coords[index][1] - coords[index - 1][1]) * local
            return (lat, lon), index - 1
    return coords[-1], len(coords) - 1


def sample_targets(distance_mi: float, interval_mi: float) -> list[float]:
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    if distance_mi <= 0.05:
        return [0.0]
    targets = [0.0]
    cursor = float(interval_mi)
    while cursor < distance_mi - 0.05:
        targets.append(round(cursor, 4))
        cursor += interval_mi
    targets.append(round(distance_mi, 4))
    return targets


def sample_route(
    coords: list[tuple[float, float]],
    distance_mi: float,
    duration_seconds: float,
    interval_mi: float,
    steps: list[dict] | None = None,
) -> list[SamplePoint]:
    if not coords:
        raise ValueError("route geometry is empty")

    table = _mile_duration_table(steps, distance_mi, duration_seconds)
    cumulative = cumulative_miles(coords)
    points: list[SamplePoint] = []
    for mile in sample_targets(max(0.0, distance_mi), interval_mi):
        fraction = 0.0 if distance_mi <= 0 else mile / distance_mi
        (lat, lon), vertex = _point_at_fraction(coords, cumulative, fraction)
        points.append(
            SamplePoint(
                lat=lat,
                lon=lon,
                mile=round(mile, 2),
                eta_offset_seconds=round(duration_at_mile(table, mile), 1),
                vertex=vertex,
            )
        )
    if points:
        points[-1] = SamplePoint(
            lat=coords[-1][0],
            lon=coords[-1][1],
            mile=round(max(distance_mi, 0.0), 2),
            eta_offset_seconds=round(duration_seconds, 1),
            vertex=len(coords) - 1,
        )
    return points


def simplify_line(
    coords: list[tuple[float, float]],
    keep: set[int],
    min_miles: float = 0.2,
) -> tuple[list[tuple[float, float]], dict[int, int]]:
    """Drop dense shape points while keeping every checkpoint vertex."""
    if len(coords) <= 2:
        return list(coords), {index: index for index in range(len(coords))}

    chosen = [0]
    anchor = coords[0]
    last_index = len(coords) - 1
    for index in range(1, last_index):
        point = coords[index]
        if index in keep or haversine_miles(anchor[0], anchor[1], point[0], point[1]) >= min_miles:
            chosen.append(index)
            anchor = point
    chosen.append(last_index)
    mapping = {old: new for new, old in enumerate(chosen)}
    return [coords[index] for index in chosen], mapping


def resample_line(coords: list[tuple[float, float]], every_miles: float) -> list[tuple[float, float]]:
    if not coords:
        return []
    kept = [coords[0]]
    carried = 0.0
    for start, end in zip(coords, coords[1:]):
        carried += haversine_miles(start[0], start[1], end[0], end[1])
        if carried >= every_miles:
            kept.append(end)
            carried = 0.0
    if kept[-1] != coords[-1]:
        kept.append(coords[-1])
    return kept
