"""Module 6 — Forecast Engine: time-series + trend (steps 1-5).
ASSUMPTION: app.models/app.db same as Module 5."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from app.core.db import get_session         # ASSUMPTION
from app.models import BeachForecast   # ASSUMPTION

DELTA_HOURS = [1, 3, 6, 12, 24]


@dataclass
class TimeSeriesPoint:
    forecast_time: datetime
    wave_height: Optional[float]
    current_speed: Optional[float]
    wind_speed: Optional[float]


def load_series(session, beach_id: str, hours_ahead: int = 30) -> list[TimeSeriesPoint]:
    """step 1-2: beach-wise time series, hourly slices, forward-looking window."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(BeachForecast)
        .where(
            BeachForecast.beach_id == beach_id,
            BeachForecast.forecast_time >= now,
            BeachForecast.forecast_time <= now + timedelta(hours=hours_ahead),
        )
        .order_by(BeachForecast.forecast_time.asc())
    )
    return [
        TimeSeriesPoint(r.forecast_time, r.wave_height, r.current_speed, r.wind_speed)
        for r in session.execute(stmt).scalars()
    ]


def compute_deltas(series: list[TimeSeriesPoint], base_time: datetime) -> dict[int, Optional[float]]:
    """step 3: 1h/3h/6h/12h/24h wave-height delta vs base_time."""
    base_val = _nearest_value(series, base_time)
    out: dict[int, Optional[float]] = {}
    for h in DELTA_HOURS:
        target = base_time + timedelta(hours=h)
        val = _nearest_value(series, target)
        out[h] = None if (base_val is None or val is None) else round(val - base_val, 3)
    return out


def trend_slope(series: list[TimeSeriesPoint], hours: int = 6) -> Optional[float]:
    """step 4: simple linear slope of wave_height over trailing `hours` window (m/hr)."""
    if len(series) < 2:
        return None
    pts = [(p.forecast_time, p.wave_height) for p in series if p.wave_height is not None]
    if len(pts) < 2:
        return None
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 3600.0 for t, _ in pts]
    ys = [float(v) for _, v in pts]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs) or 1e-6
    return round(num / den, 5)


def _nearest_value(series: list[TimeSeriesPoint], t: datetime) -> Optional[float]:
    if not series:
        return None
    closest = min(series, key=lambda p: abs((p.forecast_time - t).total_seconds()))
    if abs((closest.forecast_time - t).total_seconds()) > 3600:
        return None  # no point within 1hr -> don't fabricate a value
    return closest.wave_height
