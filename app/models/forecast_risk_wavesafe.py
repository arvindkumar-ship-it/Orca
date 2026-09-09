"""Module 2C â€” Forecast & risk tables. Matches exact SQL: beach_activity_profiles,
beach_forecasts, hazard_alerts, beach_risk_scores, trip_plans, trip_risk_snapshots."""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Numeric, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone

from .base import Base, uuid_pk


class BeachActivityProfile(Base):
    __tablename__ = "beach_activity_profiles"
    __table_args__ = (UniqueConstraint("beach_id", "activity_type", name="uniq_beach_activity"),)
    id = uuid_pk()
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)
    min_safe_wave_height = Column(Numeric(8, 3))
    max_safe_current_speed = Column(Numeric(8, 3))
    max_safe_wind_speed = Column(Numeric(8, 3))
    max_safe_swell = Column(Numeric(8, 3))
    water_quality_min = Column(Numeric(8, 3))
    tide_sensitivity = Column(Numeric(8, 3))
    risk_weights = Column(JSONB, nullable=False, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class BeachForecast(Base):
    __tablename__ = "beach_forecasts"
    __table_args__ = (Index("idx_beach_forecasts_beach_time", "beach_id", "forecast_time"),)
    id = uuid_pk()
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="CASCADE"), nullable=False)
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


class HazardAlert(Base):
    __tablename__ = "hazard_alerts"
    __table_args__ = (Index("idx_hazard_alerts_validity", "valid_from", "valid_to"),)
    id = uuid_pk()
    source_system = Column(Text, nullable=False)
    source_alert_id = Column(Text)
    alert_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    title = Column(Text)
    description = Column(Text)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False))
    issued_at = Column(DateTime(timezone=True), nullable=False)
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    eta_minutes = Column(Integer)
    hard_override_flag = Column(Boolean, default=False)
    raw_payload = Column(JSONB)
    status = Column(Text, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class BeachRiskScore(Base):
    __tablename__ = "beach_risk_scores"
    __table_args__ = (Index("idx_risk_scores_lookup", "beach_id", "activity_type", "forecast_time"),)
    id = uuid_pk()
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)
    forecast_time = Column(DateTime(timezone=True), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    risk_score = Column(Numeric(8, 5), nullable=False)
    verdict = Column(Text, nullable=False)
    explanation = Column(JSONB, nullable=False, default=dict)
    hard_override_reason = Column(Text)
    version = Column(Integer, nullable=False, default=1)


class TripStatus:
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TripRecommendation:
    GO = "go"
    CAUTION = "caution"
    AVOID_TRIP = "avoid_trip"


class TripPlan(Base):
    __tablename__ = "trip_plans"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id"), nullable=False)
    activity_type = Column(Text, nullable=False)
    planned_from = Column(DateTime(timezone=True), nullable=False)
    planned_to = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class TripRiskSnapshot(Base):
    __tablename__ = "trip_risk_snapshots"
    id = uuid_pk()
    trip_plan_id = Column(UUID(as_uuid=True), ForeignKey("trip_plans.id", ondelete="CASCADE"), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    min_risk = Column(Numeric(8, 5))
    max_risk = Column(Numeric(8, 5))
    recommendation = Column(Text)
    safe_window_start = Column(DateTime(timezone=True))
    safe_window_end = Column(DateTime(timezone=True))
    explanation = Column(JSONB, nullable=False, default=dict)

