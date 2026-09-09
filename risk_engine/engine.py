"""ORCA — GENERALIZE of risk_engine/engine.py (all 10 steps, uncommented and
completed — the source file was a commented-out draft). beach_id->zone_id,
BeachRiskScore->ZoneRiskScore, load_beach->load_zone throughout."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.db import get_session
from app.models.forecast_risk import ZoneRiskScore
from app.redis_client import redis_client

from .data_loaders import (
    build_feature_window, extract_current_features, load_active_hazard_alerts,
    load_activity_profile, load_zone, load_latest_forecast, load_trend_forecast,
)
from .scoring import compute_risk

logger = logging.getLogger("risk_engine")

RISK_CACHE_TTL_SECONDS = 900
RISK_UPDATE_CHANNEL = "notification_engine:risk_updated"
TREND_LOOKBACK_HOURS = 24


def compute_and_store_risk(zone_id: str, activity_type: str) -> Optional[dict]:
    with get_session() as session:
        zone = load_zone(session, zone_id)
        profile = load_activity_profile(session, zone_id, activity_type)
        if zone is None or profile is None:
            logger.warning("risk_engine.skip zone_id=%s activity=%s reason=missing_profile", zone_id, activity_type)
            return None

        forecast = load_latest_forecast(session, zone_id)
        if forecast is None:
            logger.warning("risk_engine.skip zone_id=%s reason=no_forecast", zone_id)
            return None

        active_alerts = load_active_hazard_alerts(session, zone_id)
        active_alert_types = [a.alert_type for a in active_alerts]

        features = extract_current_features(forecast, zone)
        feature_window = build_feature_window(session, zone_id)
        medians_iqrs = {k: feature_window.median_iqr(k) for k in features}

        prior = load_trend_forecast(session, zone_id, TREND_LOOKBACK_HOURS)
        delta_trend = _wave_delta(forecast, prior)
        delta_tide = _tide_delta(forecast, prior)
        delta_coverage = 0.0  # lifeguard/patrol coverage has no forecast trend; static per current hour

        weights = profile.risk_weights or None  # None -> DEFAULT_WEIGHTS in scoring.py

        risk_score, verdict, explanation = compute_risk(
            features=features, medians_iqrs=medians_iqrs, active_alert_types=active_alert_types,
            delta_trend=delta_trend, delta_tide=delta_tide, delta_coverage=delta_coverage, weights=weights,
        )
        override_reason = explanation.hard_override_reason

        row = ZoneRiskScore(
            marine_zone_id=zone_id, activity_type=activity_type, forecast_time=forecast.forecast_time,
            risk_score=risk_score, verdict=verdict, explanation=explanation.to_dict(),
            hard_override_reason=override_reason,
        )
        session.add(row)
        session.commit()
        row_id = str(row.id)
        forecast_time_str = forecast.forecast_time.isoformat()

    result = {
        "zone_risk_score_id": row_id, "zone_id": zone_id, "forecast_time": forecast_time_str,
        "activity_type": activity_type, "risk_score": risk_score, "verdict": verdict,
        "hard_override_reason": override_reason, "computed_at": datetime.now(timezone.utc).isoformat(),
        "explanation": explanation.to_dict(),
    }

    _publish_to_cache(result)
    _publish_to_notification_engine(result)

    logger.info("risk_engine.computed zone_id=%s activity=%s verdict=%s score=%.4f override=%s",
                zone_id, activity_type, verdict, risk_score, override_reason)
    return result


def _wave_delta(forecast, prior) -> float:
    if prior is None or forecast.wave_height is None or prior.wave_height is None:
        return 0.0
    return float(forecast.wave_height) - float(prior.wave_height)


def _tide_delta(forecast, prior) -> float:
    from .features import tide_state_to_risk
    if prior is None:
        return 0.0
    return tide_state_to_risk(forecast.tide_state) - tide_state_to_risk(prior.tide_state)


def _publish_to_cache(result: dict) -> None:
    key = f"risk_score:{result['zone_id']}:{result['activity_type']}"
    redis_client.set(key, json.dumps(result, default=str), ex=RISK_CACHE_TTL_SECONDS)


def _publish_to_notification_engine(result: dict) -> None:
    redis_client.publish(RISK_UPDATE_CHANNEL, json.dumps(result, default=str))
