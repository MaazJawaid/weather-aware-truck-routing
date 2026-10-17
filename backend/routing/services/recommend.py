"""Turn checkpoint risk into mile totals and pick a route.

Sort, safest first:
1. fewest no-travel miles
2. fewest severe miles
3. fewest high miles
4. fewest unknown miles (missing weather must not rank as a clean low-risk trip)
5. lowest mile-weighted average risk
6. shortest travel time
"""

from __future__ import annotations

from routing.services.risk import SCORE, merge_risk


def build_segments(checkpoints: list[dict]) -> list[dict]:
    segments = []
    for left, right in zip(checkpoints, checkpoints[1:]):
        start = int(left["vertex"])
        end = int(right["vertex"])
        if end < start:
            start, end = end, start
        segments.append(
            {
                "from_vertex": start,
                "to_vertex": end,
                "miles": round(max(0.0, float(right["mile"]) - float(left["mile"])), 2),
                "risk": merge_risk(left["risk"], right["risk"]),
            }
        )
    return segments


def summarize_segments(segments: list[dict], distance_mi: float, duration_seconds: float) -> dict:
    totals = {name: 0.0 for name in (*SCORE.keys(), "unknown")}
    weighted = 0.0
    known_miles = 0.0
    for segment in segments:
        risk = segment["risk"]
        miles = float(segment["miles"])
        totals[risk] = totals.get(risk, 0.0) + miles
        if risk in SCORE:
            weighted += SCORE[risk] * miles
            known_miles += miles
    average = round(weighted / known_miles, 3) if known_miles else None
    return {
        "distance_mi": round(float(distance_mi), 1),
        "duration_seconds": int(round(duration_seconds)),
        "duration_min": int(round(duration_seconds / 60)),
        "no_travel_miles": round(totals["no_travel"], 1),
        "severe_miles": round(totals["severe"], 1),
        "high_miles": round(totals["high"], 1),
        "moderate_miles": round(totals["moderate"], 1),
        "low_miles": round(totals["low"], 1),
        "unknown_miles": round(totals["unknown"], 1),
        "average_risk": average,
    }


def rank_key(route: dict) -> tuple:
    summary = route["summary"]
    average = summary["average_risk"]
    return (
        summary["no_travel_miles"],
        summary["severe_miles"],
        summary["high_miles"],
        summary["unknown_miles"],
        average if average is not None else 1_000_000,
        summary["duration_seconds"],
    )


def rank_routes(routes: list[dict]) -> list[dict]:
    return sorted(routes, key=rank_key)


def explain_ranking(winner: dict) -> str:
    summary = winner["summary"]
    average = summary["average_risk"]
    average_text = "n/a" if average is None else f"{average:.2f}"
    return (
        "Ranked by fewest no-travel miles "
        f"({summary['no_travel_miles']}), then severe miles ({summary['severe_miles']}), "
        f"high miles ({summary['high_miles']}), unknown miles ({summary['unknown_miles']}), "
        f"average risk ({average_text}), then travel time."
    )
