# forecast_engine/open_meteo_connector.py
# NEW FILE — additive only, does not touch any existing file.
# Marine endpoint: VERIFIED real. Weather endpoint: VERIFIED real (curl confirmed m/s, mm, m units).

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.forecast_risk import BeachForecast

logger = logging.getLogger(__name__)

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

SOURCE_NAME = "open-meteo"


class ForecastProviderError(RuntimeError):
    pass


def _fetch_marine(client: httpx.Client, lat: float, lon: float, days: int) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wave_height,swell_wave_height,ocean_current_velocity,sea_level_height_msl",
        "forecast_days": days,
        "timezone": "GMT",
        "cell_selection": "sea",
        "length_unit": "metric",
    }
    resp = client.get(MARINE_URL, params=params)
    if resp.status_code != 200:
        raise ForecastProviderError(f"Marine API failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _fetch_weather(client: httpx.Client, lat: float, lon: float, days: int) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,rain,precipitation,visibility",
        "forecast_days": days,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }
    resp = client.get(WEATHER_URL, params=params)
    if resp.status_code != 200:
        raise ForecastProviderError(f"Weather API failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _as_map(payload: dict[str, Any], field: str) -> dict[datetime, float | None]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    values = hourly.get(field, [])
    return {_parse_time(t): v for t, v in zip(times, values)}


def normalize_forecasts(
    beach_id: UUID,
    marine_payload: dict[str, Any],
    weather_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    marine_times = [_parse_time(t) for t in marine_payload.get("hourly", {}).get("time", [])]

    wave_map = _as_map(marine_payload, "wave_height")
    swell_map = _as_map(marine_payload, "swell_wave_height")
    sea_level_map = _as_map(marine_payload, "sea_level_height_msl")
    current_map_kmh = _as_map(marine_payload, "ocean_current_velocity")

    wind_map: dict[datetime, float | None] = {}
    rain_map: dict[datetime, float | None] = {}
    precip_map: dict[datetime, float | None] = {}
    visibility_map: dict[datetime, float | None] = {}
    if weather_payload is not None:
        wind_map = _as_map(weather_payload, "wind_speed_10m")
        rain_map = _as_map(weather_payload, "rain")
        precip_map = _as_map(weather_payload, "precipitation")
        visibility_map = _as_map(weather_payload, "visibility")

    marine_grid_lat = marine_payload.get("latitude")
    marine_grid_lon = marine_payload.get("longitude")
    weather_grid_lat = weather_payload.get("latitude") if weather_payload else None
    weather_grid_lon = weather_payload.get("longitude") if weather_payload else None
    sorted_times = sorted(sea_level_map.keys())
    tide_direction_map: dict[datetime, str | None] = {}
    for i in range(1, len(sorted_times)):
        prev_t, curr_t = sorted_times[i - 1], sorted_times[i]
        prev_val, curr_val = sea_level_map.get(prev_t), sea_level_map.get(curr_t)
        if prev_val is not None and curr_val is not None:
            tide_direction_map[curr_t] = "rising" if curr_val > prev_val else "falling" if curr_val < prev_val else "steady"
    rows = []
    for t in marine_times:
        current_kmh = current_map_kmh.get(t)
        current_ms = round(current_kmh / 3.6, 3) if current_kmh is not None else None

        rainfall = rain_map.get(t)
        if rainfall is None:
            rainfall = precip_map.get(t)

        rows.append({
            "beach_id": beach_id,
            "forecast_time": t,
            "wave_height": wave_map.get(t),
            "current_speed": current_ms,
            "wind_speed": wind_map.get(t),
            "swell_height": swell_map.get(t),
            "tide_state": tide_direction_map.get(t),
            "rainfall": rainfall,
            "visibility": visibility_map.get(t),
            "water_quality": None,
            "source": SOURCE_NAME,
            "raw_payload": {
                "marine": marine_payload,
                "weather": weather_payload,
                "requested_lat": None,
                "requested_lon": None,
                "marine_grid_lat": marine_grid_lat,
                "marine_grid_lon": marine_grid_lon,
                "weather_grid_lat": weather_grid_lat,
                "weather_grid_lon": weather_grid_lon,
                "sea_level_height_msl_m": sea_level_map.get(t),
            },
        })
    return rows


def _upsert_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    for row in rows:
        exists = db.execute(
            select(BeachForecast.id).where(
                BeachForecast.beach_id == row["beach_id"],
                BeachForecast.forecast_time == row["forecast_time"],
                BeachForecast.source == row["source"],
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(BeachForecast(**row))
        inserted += 1
    db.commit()
    return inserted


def sync_beach_forecast(beach_id: UUID, lat: float, lon: float, forecast_days: int = 7) -> int:
    with httpx.Client(timeout=20.0) as client:
        marine = _fetch_marine(client, lat, lon, forecast_days)
        try:
            weather = _fetch_weather(client, lat, lon, forecast_days)
        except ForecastProviderError:
            logger.exception("Weather fetch failed for beach_id=%s, proceeding marine-only", beach_id)
            weather = None

    rows = normalize_forecasts(beach_id, marine, weather)
    for r in rows:
        r["raw_payload"]["requested_lat"] = lat
        r["raw_payload"]["requested_lon"] = lon

    with get_session() as db:
        count = _upsert_rows(db, rows)

    logger.info("open-meteo sync beach_id=%s inserted=%s of %s rows", beach_id, count, len(rows))
    return count