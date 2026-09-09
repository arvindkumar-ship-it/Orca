"""
ORCA — GENERALIZE of app/models/forecast_risk.py.

beach_activity_profiles -> zone_activity_profiles (beach_id -> marine_zone_id)
beach_forecasts         -> zone_forecasts         (beach_id -> marine_zone_id)
beach_risk_scores       -> zone_risk_scores        (beach_id -> marine_zone_id)

HazardAlert is COPY — unchanged, not redefined here (import from WaveSafe's
original file). It was already geometry-generic (ST_Intersects against
whatever polygon you join it to), so it works against marine_zones without
any change.

TripPlan/TripRiskSnapshot are intentionally NOT ported — per the build
spec's reuse matrix, trip_service.py's logic is lifted into
route_optimizer/, not the file itself; a "trip" table tied to a single
beach_id doesn't fit the route-planning flow this project uses instead.
"""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Numeric, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone

from app.models.base import Base, uuid_pk

# Re-export — same reasoning as geospatial.py's re-export block. Confirmed
# via repo-wide grep: trip_service.py, admin_service.py, trips.py,
# open_meteo_connector.py all import directly from this submodule path.
from app.models.forecast_risk_wavesafe import (  # noqa: F401
    BeachActivityProfile, BeachForecast, HazardAlert, BeachRiskScore,
    TripStatus, TripRecommendation, TripPlan, TripRiskSnapshot,
)


class ZoneActivityProfile(Base):
    __tablename__ = "zone_activity_profiles"
    __table_args__ = (UniqueConstraint("marine_zone_id", "activity_type", name="uniq_zone_activity"),)
    id = uuid_pk()
    marine_zone_id = Column(UUID(as_uuid=True), ForeignKey("marine_zones.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)  # 'fishing' | 'navigation' | 'diving'
    min_safe_wave_height = Column(Numeric(8, 3))
    max_safe_current_speed = Column(Numeric(8, 3))
    max_safe_wind_speed = Column(Numeric(8, 3))
    max_safe_swell = Column(Numeric(8, 3))
    water_quality_min = Column(Numeric(8, 3))
    tide_sensitivity = Column(Numeric(8, 3))
    risk_weights = Column(JSONB, nullable=False, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ZoneForecast(Base):
    __tablename__ = "zone_forecasts"
    __table_args__ = (Index("idx_zone_forecasts_zone_time", "marine_zone_id", "forecast_time"),)
    id = uuid_pk()
    marine_zone_id = Column(UUID(as_uuid=True), ForeignKey("marine_zones.id", ondelete="CASCADE"), nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    wave_height = Column(Numeric(8, 3))
    current_speed = Column(Numeric(8, 3))
    wind_speed = Column(Numeric(8, 3))
    swell_height = Column(Numeric(8, 3))
    tide_state = Column(Text)
    rainfall = Column(Numeric(8, 3))
    visibility = Column(Numeric(8, 3))
    water_quality = Column(Numeric(8, 3))
    source = Column(Text, nullable=False)
    raw_payload = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ZoneRiskScore(Base):
    __tablename__ = "zone_risk_scores"
    __table_args__ = (Index("idx_zone_risk_scores_lookup", "marine_zone_id", "activity_type", "forecast_time"),)
    id = uuid_pk()
    marine_zone_id = Column(UUID(as_uuid=True), ForeignKey("marine_zones.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    risk_score = Column(Numeric(8, 5), nullable=False)
    verdict = Column(Text, nullable=False)
    explanation = Column(JSONB, nullable=False, default=dict)
    hard_override_reason = Column(Text)
    version = Column(Integer, nullable=False, default=1)
