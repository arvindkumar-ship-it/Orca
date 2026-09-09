"""Module 6 — Forecast Engine: orchestrator (steps 1,10,11).
ASSUMPTION: BeachRiskScore reused from Module 5 model; redis_client from
app.redis_client for trip-planner signal (Module 7 subscribes)."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from app.core.db import get_session            # ASSUMPTION
from app.redis_client import redis_client  # ASSUMPTION

from .timeseries import compute_deltas, load_series, trend_slope
from .outlook import build_outlook, score_series

logger = logging.getLogger("forecast_engine")
TRIP_SIGNAL_CHANNEL = "trip_planner:forecast_updated"


def compute_forecast_outlook(beach_id: str, activity_type: str) -> dict:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        series = load_series(session, beach_id)              # steps 1-2
        deltas = compute_deltas(series, now)                  # step 3
        slope = trend_slope(series)                           # step 4
        risk_points = score_series(session, beach_id, activity_type, series)  # step 5-6
        outlook = build_outlook(risk_points, now)              # steps 6-8

        risk_by_time = {rp.forecast_time: rp for rp in risk_points}
        points = [
            {
                "forecast_time": sp.forecast_time.isoformat(),
                "wave_height": sp.wave_height,
                "current_speed": sp.current_speed,
                "wind_speed": sp.wind_speed,
                "risk_score": risk_by_time[sp.forecast_time].risk_score if sp.forecast_time in risk_by_time else None,
                "verdict": risk_by_time[sp.forecast_time].verdict if sp.forecast_time in risk_by_time else None,
            }
            for sp in series
        ]

    result = {
        "beach_id": beach_id,
        "points": points,
        "activity_type": activity_type,
        "computed_at": now.isoformat(),
        "current_verdict": outlook.current_verdict,
        "current_risk": outlook.current_risk,
        "window_3h": outlook.window_3h,
        "window_12h": outlook.window_12h,
        "safe_window_start": outlook.safe_window_start.isoformat() if outlook.safe_window_start else None,
        "safe_window_end": outlook.safe_window_end.isoformat() if outlook.safe_window_end else None,
        "no_go_windows": [(s.isoformat(), e.isoformat()) for s, e in outlook.no_go_windows],
        "expected_improvement_time": outlook.expected_improvement_time.isoformat() if outlook.expected_improvement_time else None,
        "confidence": outlook.confidence,
        "wave_height_deltas": deltas,
        "trend_slope_m_per_hr": slope,
    }

    _save_curve(result)      # step 10
    _signal_trip_planner(result)  # step 11
    logger.info("forecast_engine.computed beach_id=%s activity=%s verdict=%s conf=%.2f",
                beach_id, activity_type, outlook.current_verdict, outlook.confidence)
    return result


def _save_curve(result: dict) -> None:
    key = f"forecast_outlook:{result['beach_id']}:{result['activity_type']}"
    redis_client.set(key, json.dumps(result, default=str), ex=3600)


def _signal_trip_planner(result: dict) -> None:
    redis_client.publish(TRIP_SIGNAL_CHANNEL, json.dumps(result, default=str))
