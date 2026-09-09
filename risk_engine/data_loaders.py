"""
ORCA — GENERALIZE of risk_engine/data_loaders.py.

load_beach -> load_zone, MarineZone/ZoneActivityProfile/ZoneForecast replace
Beach/BeachActivityProfile/BeachForecast throughout. HazardAlert import
unchanged (COPY table, joined against marine_zones.geom instead of
beaches.geom — same ST_Intersects mechanism).

risk_engine/features.py needs NO changes — COPY, not redefined here. It
operates on plain feature dicts (FEATURE_KEYS/FeatureWindow/robust_zscore),
with no beach-specific coupling, so it works unmodified against zone data.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.core.db import get_session
from app.models.geospatial import MarineZone
from app.models.forecast_risk import ZoneActivityProfile, ZoneForecast
from app.models.forecast_risk_wavesafe import HazardAlert  # COPY: WaveSafe's original app/models/forecast_risk.py,
# copied verbatim under this filename so it doesn't clash with ORCA's own forecast_risk.py (Zone* tables) above.

from .features import FeatureWindow, coverage_gap, tide_state_to_risk

# Re-export — forecast_engine/outlook.py (COPY, unchanged) imports
# `load_beach` from this module by name at module load time. Found and
# fixed during the real merge/import test (see data_loaders_wavesafe.py).
from risk_engine.data_loaders_wavesafe import load_beach  # noqa: F401

TREND_WINDOW_HOURS = 24
HISTORY_DAYS_FOR_IQR = 30


def load_zone(session, zone_id: str) -> Optional[MarineZone]:
    return session.get(MarineZone, zone_id)


def load_activity_profile(session, zone_id: str, activity_type: str) -> Optional[ZoneActivityProfile]:
    stmt = select(ZoneActivityProfile).where(
        ZoneActivityProfile.marine_zone_id == zone_id,
        ZoneActivityProfile.activity_type == activity_type,
        ZoneActivityProfile.active.is_(True),
    )
    return session.execute(stmt).scalar_one_or_none()


def load_latest_forecast(session, zone_id: str) -> Optional[ZoneForecast]:
    """Nearest upcoming forecast slot (>= now), falling back to the most
    recent past slot if nothing upcoming is stored yet — same two-step
    lookup and same bug-fix rationale as the original beach_service.py
    (previously ORDER BY DESC with no lower bound could return a
    far-future anomalous row instead of the current slot)."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(ZoneForecast)
        .where(ZoneForecast.marine_zone_id == zone_id, ZoneForecast.forecast_time >= now)
        .order_by(ZoneForecast.forecast_time.asc())
        .limit(1)
    )
    forecast = session.execute(stmt).scalar_one_or_none()
    if forecast is not None:
        return forecast

    stmt = (
        select(ZoneForecast)
        .where(ZoneForecast.marine_zone_id == zone_id, ZoneForecast.forecast_time < now)
        .order_by(ZoneForecast.forecast_time.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def load_trend_forecast(session, zone_id: str, hours_ago: int) -> Optional[ZoneForecast]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    stmt = (
        select(ZoneForecast)
        .where(ZoneForecast.marine_zone_id == zone_id, ZoneForecast.forecast_time <= cutoff)
        .order_by(ZoneForecast.forecast_time.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def load_active_hazard_alerts(session, zone_id: str) -> list[HazardAlert]:
    """Alerts whose geometry intersects the zone and are currently valid."""
    from geoalchemy2.functions import ST_Intersects
    now = datetime.now(timezone.utc)
    stmt = (
        select(HazardAlert, MarineZone.geom)
        .join(MarineZone, MarineZone.id == zone_id)
        .where(
            HazardAlert.status == "active",
            HazardAlert.valid_from <= now,
            (HazardAlert.valid_to.is_(None)) | (HazardAlert.valid_to >= now),
            ST_Intersects(HazardAlert.geom, MarineZone.geom),
        )
    )
    rows = session.execute(stmt).all()
    return [r[0] for r in rows]


def build_feature_window(session, zone_id: str) -> FeatureWindow:
    """Trailing history for robust median/IQR normalization."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS_FOR_IQR)
    stmt = select(ZoneForecast).where(ZoneForecast.marine_zone_id == zone_id, ZoneForecast.forecast_time >= cutoff)
    fw = FeatureWindow()
    for row in session.execute(stmt).scalars():
        fw.add({
            "wave_height": row.wave_height, "current_speed": row.current_speed,
            "wind_speed": row.wind_speed, "swell_height": row.swell_height,
            "water_quality": row.water_quality, "rainfall": row.rainfall,
            "tide_risk": tide_state_to_risk(row.tide_state),
            "coverage_gap": 0.0,  # coverage isn't forecast-driven; excluded from history stats
        })
    return fw


def extract_current_features(forecast: ZoneForecast, zone: MarineZone, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {
        "wave_height": forecast.wave_height, "current_speed": forecast.current_speed,
        "wind_speed": forecast.wind_speed, "swell_height": forecast.swell_height,
        "water_quality": forecast.water_quality, "rainfall": forecast.rainfall,
        "tide_risk": tide_state_to_risk(forecast.tide_state),
        "coverage_gap": coverage_gap(zone.has_lifeguard, now.hour),
    }
