"""Open-Meteo hourly forecasts, batched and cached by rounded coordinate."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MM_PER_INCH = 25.4
CM_PER_INCH = 2.54
BATCH_SIZE = 40
CACHE_SECONDS = 60 * 30


@dataclass(frozen=True)
class Hour:
    time: datetime
    wind_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None


def floor_hour(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        aware = moment.replace(tzinfo=timezone.utc)
    else:
        aware = moment.astimezone(timezone.utc)
    return aware.replace(minute=0, second=0, microsecond=0)


def _parse_time(stamp: str) -> datetime:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def hours_from_block(block: dict) -> list[Hour]:
    hourly = block.get("hourly") or {}
    times = hourly.get("time") or []
    winds = hourly.get("wind_speed_10m") or []
    rains = hourly.get("rain") or []
    snows = hourly.get("snowfall") or []
    hours: list[Hour] = []
    for stamp, wind, rain, snow in zip(times, winds, rains, snows):
        rain_mm = _optional(rain)
        snow_cm = _optional(snow)
        hours.append(
            Hour(
                time=_parse_time(stamp),
                wind_mph=_optional(wind),
                rain_in_hr=None if rain_mm is None else rain_mm / MM_PER_INCH,
                snow_in_hr=None if snow_cm is None else snow_cm / CM_PER_INCH,
            )
        )
    return hours


def parse_forecast_payload(payload: dict | list) -> dict[tuple[float, float], list[Hour]]:
    blocks = payload if isinstance(payload, list) else [payload]
    parsed: dict[tuple[float, float], list[Hour]] = {}
    for block in blocks:
        if not isinstance(block, dict) or "latitude" not in block:
            continue
        key = (round(float(block["latitude"]), 2), round(float(block["longitude"]), 2))
        parsed[key] = hours_from_block(block)
    return parsed


def _cache_id(key: tuple[float, float]) -> str:
    return f"wx:{key[0]:.2f}:{key[1]:.2f}"


def _fetch_batch(keys: list[tuple[float, float]]) -> dict[tuple[float, float], list[Hour]]:
    if not keys:
        return {}
    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": ",".join(f"{lat:.2f}" for lat, _lon in keys),
            "longitude": ",".join(f"{lon:.2f}" for _lat, lon in keys),
            "hourly": "wind_speed_10m,rain,snowfall",
            "wind_speed_unit": "mph",
            "timezone": "UTC",
            "forecast_days": 7,
        },
        timeout=30,
    )
    if response.status_code == 400 and len(keys) > 1:
        middle = len(keys) // 2
        left = _fetch_batch(keys[:middle])
        right = _fetch_batch(keys[middle:])
        return {**left, **right}
    response.raise_for_status()
    return parse_forecast_payload(response.json())


def _fetch_all(keys: list[tuple[float, float]]) -> dict[tuple[float, float], list[Hour]]:
    batches = [keys[index : index + BATCH_SIZE] for index in range(0, len(keys), BATCH_SIZE)]
    merged: dict[tuple[float, float], list[Hour]] = {}
    workers = min(4, max(1, len(batches)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_batch, batch) for batch in batches]
        for future in futures:
            try:
                merged.update(future.result())
            except requests.RequestException as exc:
                logger.warning("weather batch failed: %s", exc)
    return merged


def fetch_forecasts(coords: list[tuple[float, float]]) -> dict[tuple[float, float], list[Hour]]:
    from django.core.cache import cache

    unique = list(dict.fromkeys((round(lat, 2), round(lon, 2)) for lat, lon in coords))
    found: dict[tuple[float, float], list[Hour]] = {}
    missing: list[tuple[float, float]] = []
    for key in unique:
        cached = cache.get(_cache_id(key))
        if cached is not None:
            found[key] = cached
        else:
            missing.append(key)

    if missing:
        fetched = _fetch_all(missing)
        for key in missing:
            series = fetched.get(key, [])
            if series:
                cache.set(_cache_id(key), series, CACHE_SECONDS)
            found[key] = series
    return found


def forecast_window(now: datetime, hours: int = 49) -> list[datetime]:
    start = floor_hour(now)
    return [start + timedelta(hours=offset) for offset in range(hours)]
