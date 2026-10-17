"""Weather and load risk bands from the assessment brief.

Overlapping printed edges belong to the more severe band. Load rules only
upgrade wind, and the cutovers at 30,000 lb and 40,000 lb are strict.
"""

from __future__ import annotations

SCORE = {
    "low": 1,
    "moderate": 2,
    "high": 3,
    "severe": 4,
    "no_travel": 5,
}
RISK_CODE = {
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "high": 3,
    "severe": 4,
    "no_travel": 5,
}


def wind_band(mph: float) -> str:
    if mph >= 55:
        return "no_travel"
    if mph >= 45:
        return "severe"
    if mph >= 35:
        return "high"
    if mph >= 25:
        return "moderate"
    return "low"


def rain_band(inches_per_hour: float) -> str:
    rate = max(0.0, inches_per_hour)
    if rate > 1.0:
        return "no_travel"
    if rate >= 0.50:
        return "severe"
    if rate >= 0.25:
        return "high"
    if rate >= 0.10:
        return "moderate"
    return "low"


def snow_band(inches_per_hour: float) -> str:
    rate = max(0.0, inches_per_hour)
    if rate > 3.0:
        return "no_travel"
    if rate >= 2.0:
        return "severe"
    if rate >= 1.0:
        return "high"
    if rate >= 0.5:
        return "moderate"
    return "low"


def apply_wind_load(wind_mph: float, load_lb: float, wind_level: str) -> tuple[str, str | None]:
    """Return the wind level after the load rules, plus the upgrade that fired."""
    if wind_mph >= 55:
        return "no_travel", "load:wind>=55mph→no_travel"
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        return "no_travel", "load:45-54mph>30000lb→no_travel"
    if 35 <= wind_mph < 45 and load_lb > 40_000:
        return "severe", "load:35-44mph>40000lb→severe"
    return wind_level, None


def worst_level(*levels: str) -> str:
    known = [level for level in levels if level in SCORE]
    if not known:
        return "unknown"
    return max(known, key=lambda level: SCORE[level])


def merge_risk(left: str, right: str) -> str:
    """Segment risk is the worse endpoint. Unknown must not look like low risk."""
    known = [level for level in (left, right) if level in SCORE]
    if not known:
        return "unknown"
    worst = max(known, key=lambda level: SCORE[level])
    if "unknown" in (left, right) and SCORE[worst] <= SCORE["moderate"]:
        return "unknown"
    return worst


def classify(
    wind_mph: float | None,
    rain_in_hr: float | None,
    snow_in_hr: float | None,
    load_lb: float,
) -> dict:
    if wind_mph is None:
        return {
            "risk": "unknown",
            "rules": ["forecast_unavailable"],
            "wind_mph": None,
            "rain_in_hr": None,
            "snow_in_hr": None,
        }

    rain = 0.0 if rain_in_hr is None else max(0.0, rain_in_hr)
    snow = 0.0 if snow_in_hr is None else max(0.0, snow_in_hr)
    wind_level = wind_band(wind_mph)
    adjusted, upgrade = apply_wind_load(wind_mph, load_lb, wind_level)
    rain_level = rain_band(rain)
    snow_level = snow_band(snow)
    rules = [f"wind:{wind_level}"]
    if upgrade:
        rules.append(upgrade)
    rules.append(f"rain:{rain_level}")
    rules.append(f"snow:{snow_level}")
    return {
        "risk": worst_level(adjusted, rain_level, snow_level),
        "rules": rules,
        "wind_mph": round(float(wind_mph), 1),
        "rain_in_hr": round(rain, 3),
        "snow_in_hr": round(snow, 3),
    }
