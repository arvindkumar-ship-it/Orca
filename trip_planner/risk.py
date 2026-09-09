"""Module 7 — Trip Planner: risk computation (steps 4-9).
ASSUMPTION: app.models/app.db as in Modules 5-6."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from app.core.db import get_session          # ASSUMPTION
from app.models import Beach, BeachActivityProfile  # ASSUMPTION

from forecast_engine.timeseries import load_series
from forecast_engine.outlook import score_series, RiskPoint

ALT_BEACH_RADIUS_M = 30_000
ALT_BEACH_LIMIT = 3


@dataclass
class TripRiskResult:
    max_risk: float
    worst_verdict: str
    dangerous_slots: list[tuple[datetime, datetime]]
    points: list[RiskPoint]


def compute_trip_risk(session, beach_id: str, activity_type: str,
                       window_start: datetime, window_end: datetime) -> TripRiskResult:
    """step 5: R_trip = max over window, not average — average hides danger."""
    hours_ahead = max(1, int((window_end - datetime.now(timezone.utc)).total_seconds() // 3600) + 1)
    series = load_series(session, beach_id, hours_ahead=hours_ahead)
    series = [p for p in series if window_start <= p.forecast_time <= window_end]

    points = score_series(session, beach_id, activity_type, series)
    if not points:
        return TripRiskResult(0.0, "unknown", [], [])

    max_point = max(points, key=lambda p: p.risk_score)
    dangerous = [(p.forecast_time, p.forecast_time) for p in points if p.verdict != "safe"]
    dangerous = _merge(dangerous)

    return TripRiskResult(max_point.risk_score, max_point.verdict, dangerous, points)


def _merge(windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    windows.sort()
    merged = [windows[0]]
    for s, e in windows[1:]:
        if (s - merged[-1][1]).total_seconds() <= 3600:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def recommend_alternative_beaches(session, origin_beach_id: str, activity_type: str,
                                   window_start: datetime, window_end: datetime) -> list[dict]:
    """step 9: nearby beaches with the same activity profile, ranked by lower max risk."""
    origin = session.get(Beach, origin_beach_id)
    if origin is None:
        return []

    from geoalchemy2.functions import ST_DWithin
    stmt = (
        select(Beach.id, Beach.name)
        .join(BeachActivityProfile, BeachActivityProfile.beach_id == Beach.id)
        .where(
            Beach.id != origin_beach_id,
            Beach.active.is_(True),
            BeachActivityProfile.activity_type == activity_type,
            BeachActivityProfile.active.is_(True),
            ST_DWithin(Beach.geom, origin.geom, ALT_BEACH_RADIUS_M),
        )
        .limit(10)
    )
    candidates = session.execute(stmt).all()

    scored = []
    for beach_id, name in candidates:
        result = compute_trip_risk(session, str(beach_id), activity_type, window_start, window_end)
        if result.worst_verdict == "safe":
            scored.append({"beach_id": str(beach_id), "name": name, "max_risk": result.max_risk})

    scored.sort(key=lambda x: x["max_risk"])
    return scored[:ALT_BEACH_LIMIT]
