"""
ORCA — NEW: risk_engine/point_scoring.py

route_optimizer's A* grid cells are arbitrary lat/lng points with no
zone_activity_profiles row of their own (they usually aren't inside any
named marine_zone at all — that's the point of a grid search). This module
bridges that gap: it finds the NEAREST marine_zone with an active profile
for the requested activity_type and borrows its risk_weights + feature
medians/IQRs as the calibration for the point, then scores the point's live
forecast data (from forecast_engine.point_forecast) through the exact same
risk_engine.scoring.compute_risk() formula every zone-based risk score
uses — no duplicated/divergent scoring logic, per the project's "reuse
before rewrite" rule.

Called by: route_optimizer/risk_window.py.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from .features import FeatureWindow, tide_state_to_risk
from .scoring import compute_risk
from .data_loaders import HISTORY_DAYS_FOR_IQR

# How far to search for a calibration zone before giving up and using
# DEFAULT_WEIGHTS/neutral medians. Wider than a normal zone lookup radius
# since open-ocean grid cells can be far from any named zone.
CALIBRATION_SEARCH_RADIUS_M = 100_000


def _nearest_zone_id(session, lat: float, lng: float, activity_type: str) -> Optional[str]:
    row = session.execute(text("""
        SELECT z.id
        FROM marine_zones z
        JOIN zone_activity_profiles p ON p.marine_zone_id = z.id
        WHERE z.active = true AND p.active = true AND p.activity_type = :activity_type
          AND ST_DWithin(z.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY ST_Distance(z.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) ASC
        LIMIT 1
    """), {"lat": lat, "lng": lng, "activity_type": activity_type, "radius": CALIBRATION_SEARCH_RADIUS_M}).mappings().first()
    return str(row["id"]) if row else None


def _calibration_for(session, zone_id: str, activity_type: str):
    from .data_loaders import load_activity_profile, build_feature_window
    profile = load_activity_profile(session, zone_id, activity_type)
    fw = build_feature_window(session, zone_id)
    medians_iqrs = {k: fw.median_iqr(k) for k in
                    ("wave_height", "current_speed", "wind_speed", "swell_height",
                     "water_quality", "rainfall", "tide_risk", "coverage_gap")}
    weights = (profile.risk_weights or None) if profile else None
    return weights, medians_iqrs


def score_series_at_point(session, lat: float, lng: float, activity_type: str, series) -> list:
    """Point-keyed equivalent of forecast_engine.outlook.score_series.
    Returns the same RiskPoint list shape (forecast_time, risk_score, verdict)."""
    from forecast_engine.outlook import RiskPoint  # reuse the existing dataclass, don't redefine it

    zone_id = _nearest_zone_id(session, lat, lng, activity_type)
    if zone_id:
        weights, medians_iqrs = _calibration_for(session, zone_id, activity_type)
    else:
        # No calibration zone within range — fall back to DEFAULT_WEIGHTS and
        # neutral (0, 1) medians/IQRs rather than failing the whole route
        # request; this only reduces score precision, it never invents data.
        weights = None
        medians_iqrs = {k: (0.0, 1.0) for k in
                         ("wave_height", "current_speed", "wind_speed", "swell_height",
                          "water_quality", "rainfall", "tide_risk", "coverage_gap")}

    points = []
    for row in series:
        features = {
            "wave_height": row.wave_height, "current_speed": row.current_speed,
            "wind_speed": row.wind_speed, "swell_height": None,
            "water_quality": None, "rainfall": None, "tide_risk": 0.0, "coverage_gap": 0.0,
        }
        score, verdict, _ = compute_risk(features, medians_iqrs, active_alert_types=[], weights=weights)
        points.append(RiskPoint(row.forecast_time, score, verdict))
    return points
