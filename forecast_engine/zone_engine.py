"""
ORCA — forecast_engine/zone_engine.py (NEW)

Fixes a real integration bug found while merging: zone_service.py called
forecast_engine.engine.compute_forecast_outlook(zone_id, ...), but that
function (COPY, unchanged) is beach-keyed all the way down — it calls
outlook.score_series(session, beach_id, ...) which calls
risk_engine.data_loaders.load_beach(session, beach_id). Passing a zone_id
into a beach_id-typed function would silently query the wrong table.

Fix: this file provides a zone-keyed `score_series_zone` (parallel to
outlook.py's `score_series`, using risk_engine.data_loaders' zone-keyed
loaders instead of load_beach) and `compute_zone_forecast_outlook`. Both
`build_outlook`/`find_safe_windows` from forecast_engine/outlook.py are
reused UNCHANGED and imported directly — they only operate on a plain
`RiskPoint` list, with no beach/zone coupling at all, so nothing there
needed generalizing. forecast_engine/outlook.py and engine.py themselves
are left fully untouched (still COPY) — the beach-keyed path they serve
still works for any leftover WaveSafe code that calls it.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.forecast_risk import ZoneForecast
from risk_engine.data_loaders import build_feature_window, load_activity_profile, load_zone
from risk_engine.scoring import compute_risk
from .outlook import RiskPoint, build_outlook  # COPY, unchanged — pure point-list logic, no beach/zone coupling


def _load_future_zone_forecasts(session, zone_id: str, hours: int):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours)
    stmt = (
        select(ZoneForecast)
        .where(ZoneForecast.marine_zone_id == zone_id, ZoneForecast.forecast_time >= now,
               ZoneForecast.forecast_time <= cutoff)
        .order_by(ZoneForecast.forecast_time.asc())
    )
    return session.execute(stmt).scalars().all()


def score_series_zone(session, zone_id: str, activity_type: str, series) -> list[RiskPoint]:
    """Zone-keyed equivalent of outlook.py's score_series."""
    zone = load_zone(session, zone_id)
    profile = load_activity_profile(session, zone_id, activity_type)
    if zone is None or profile is None:
        return []
    fw = build_feature_window(session, zone_id)
    medians_iqrs = {k: fw.median_iqr(k) for k in
                     ("wave_height", "current_speed", "wind_speed", "swell_height",
                      "water_quality", "rainfall", "tide_risk", "coverage_gap")}

    points = []
    for row in series:
        features = {
            "wave_height": row.wave_height, "current_speed": row.current_speed,
            "wind_speed": row.wind_speed, "swell_height": row.swell_height,
            "water_quality": row.water_quality, "rainfall": row.rainfall,
            "tide_risk": 0.0, "coverage_gap": 0.0,
        }
        score, verdict, _ = compute_risk(features, medians_iqrs, active_alert_types=[],
                                          weights=profile.risk_weights or None)
        points.append(RiskPoint(row.forecast_time, score, verdict))
    return points


def compute_forecast_outlook(zone_id: str, activity_type: str, hours: int = 30):
    """Same name/shape as forecast_engine.engine.compute_forecast_outlook
    (what zone_service.py expects to call) but zone-keyed. zone_service.py
    is updated to import this module instead of forecast_engine.engine."""
    from app.core.db import get_session
    with get_session() as session:
        series = _load_future_zone_forecasts(session, zone_id, hours)
        points = score_series_zone(session, zone_id, activity_type, series)
        outlook = build_outlook(points, datetime.now(timezone.utc))
        return {
            "points": [{"forecast_time": p.forecast_time, "risk_score": p.risk_score, "verdict": p.verdict}
                       for p in points],
            "outlook": outlook.__dict__,
        }
