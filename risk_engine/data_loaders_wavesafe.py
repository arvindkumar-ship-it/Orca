"""risk_engine/data_loaders_wavesafe.py — WaveSafe's original beach-keyed
loaders, kept alive because forecast_engine/outlook.py (COPY, unchanged)
imports `load_beach` at module level. Same mechanism as
risk_engine/data_loaders.py's zone-keyed version, against Beach/BeachForecast
instead of MarineZone/ZoneForecast. Only `load_beach` is re-exported into
data_loaders.py (the only symbol actually missing there — see that file's
re-export note); the rest of this file exists for completeness/parity."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.models.geospatial_wavesafe import Beach
from app.models.forecast_risk_wavesafe import BeachActivityProfile, BeachForecast

from risk_engine.features import FeatureWindow, coverage_gap, tide_state_to_risk

HISTORY_DAYS_FOR_IQR = 30


def load_beach(session, beach_id: str) -> Optional[Beach]:
    return session.get(Beach, beach_id)


def load_activity_profile(session, beach_id: str, activity_type: str) -> Optional[BeachActivityProfile]:
    stmt = select(BeachActivityProfile).where(
        BeachActivityProfile.beach_id == beach_id, BeachActivityProfile.activity_type == activity_type,
        BeachActivityProfile.active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def load_latest_forecast(session, beach_id: str) -> Optional[BeachForecast]:
    now = datetime.now(timezone.utc)
    stmt = (select(BeachForecast).where(BeachForecast.beach_id == beach_id, BeachForecast.forecast_time >= now)
            .order_by(BeachForecast.forecast_time.asc()).limit(1))
    forecast = session.execute(stmt).scalar_one_or_none()
    if forecast is not None:
        return forecast
    stmt = (select(BeachForecast).where(BeachForecast.beach_id == beach_id, BeachForecast.forecast_time < now)
            .order_by(BeachForecast.forecast_time.desc()).limit(1))
    return session.execute(stmt).scalar_one_or_none()


def build_feature_window(session, beach_id: str) -> FeatureWindow:
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS_FOR_IQR)
    stmt = select(BeachForecast).where(BeachForecast.beach_id == beach_id, BeachForecast.forecast_time >= cutoff)
    fw = FeatureWindow()
    for row in session.execute(stmt).scalars():
        fw.add({
            "wave_height": row.wave_height, "current_speed": row.current_speed,
            "wind_speed": row.wind_speed, "swell_height": row.swell_height,
            "water_quality": row.water_quality, "rainfall": row.rainfall,
            "tide_risk": tide_state_to_risk(row.tide_state), "coverage_gap": 0.0,
        })
    return fw


def extract_current_features(forecast: BeachForecast, beach: Beach, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {
        "wave_height": forecast.wave_height, "current_speed": forecast.current_speed,
        "wind_speed": forecast.wind_speed, "swell_height": forecast.swell_height,
        "water_quality": forecast.water_quality, "rainfall": forecast.rainfall,
        "tide_risk": tide_state_to_risk(forecast.tide_state),
        "coverage_gap": coverage_gap(beach.has_lifeguard, now.hour),
    }
