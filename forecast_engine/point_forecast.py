"""
ORCA — NEW: forecast_engine/point_forecast.py

route_optimizer's A* grid cells are arbitrary lat/lng points, not named
marine_zones — there is no beach_id/zone_id to key a persisted
BeachForecast row against, and persisting a forecast row per transient grid
cell (potentially thousands per route request) would bloat that table for
no reuse benefit. This file fetches directly from Open-Meteo per point and
returns in-memory TimeSeriesPoint objects, reusing
open_meteo_connector.py's exact `_fetch_marine`/`_fetch_weather`/`_as_map`
functions (imported, not duplicated) — only `normalize_forecasts` and the
DB upsert step are skipped.

Depends on: forecast_engine/open_meteo_connector.py (COPY, unchanged).
Called by: route_optimizer/risk_window.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from forecast_engine.open_meteo_connector import (
    _fetch_marine, _fetch_weather, _as_map, ForecastProviderError,
)
from forecast_engine.timeseries import TimeSeriesPoint


def load_series_at_point(session, lat: float, lng: float, hours_ahead: int = 30) -> list[TimeSeriesPoint]:
    """Point-keyed equivalent of forecast_engine.timeseries.load_series.
    `session` is accepted (unused) only to keep the call signature
    consistent with every other loader in this codebase that takes a DB
    session first — this one simply doesn't need it, since nothing is
    read from or written to the database."""
    days = max(1, (hours_ahead // 24) + 1)
    with httpx.Client(timeout=15.0) as client:
        marine = _fetch_marine(client, lat, lng, days)
        try:
            weather = _fetch_weather(client, lat, lng, days)
        except ForecastProviderError:
            weather = None

    wave_map = _as_map(marine, "wave_height")
    current_map_kmh = _as_map(marine, "ocean_current_velocity")
    wind_map = _as_map(weather, "wind_speed_10m") if weather else {}

    now = datetime.now(timezone.utc)
    points: list[TimeSeriesPoint] = []
    for t in sorted(wave_map.keys()):
        if t < now:
            continue
        current_kmh = current_map_kmh.get(t)
        current_ms: Optional[float] = round(current_kmh / 3.6, 3) if current_kmh is not None else None
        points.append(TimeSeriesPoint(
            forecast_time=t, wave_height=wave_map.get(t),
            current_speed=current_ms, wind_speed=wind_map.get(t),
        ))
        if (t - now).total_seconds() > hours_ahead * 3600:
            break
    return points
