import uuid
from sqlalchemy import Column, ForeignKey, Numeric, String, Boolean, DateTime, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from app.models.base import Base


class SafeZoneGuidance(Base):
    __tablename__ = "safezone_guidance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"), nullable=True)
    trip_plan_id = Column(UUID(as_uuid=True), ForeignKey("trip_plans.id", ondelete="SET NULL"), nullable=True)
    origin_geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    safe_zone_id = Column(UUID(as_uuid=True), ForeignKey("safe_zones.id"), nullable=False)
    route_geom = Column(Geometry(geometry_type="LINESTRING", srid=4326), nullable=False)
    distance_m = Column(Numeric(10, 2), nullable=False)
    elevation_gain_m = Column(Numeric(8, 2))
    hazard_exposure = Column(Numeric(6, 3), nullable=False, default=0)
    crowd_risk = Column(Numeric(6, 3), nullable=False, default=0)
    route_score = Column(Numeric(8, 5), nullable=False)
    eta_minutes = Column(Numeric(6, 2), nullable=False)
    instruction_text = Column(String, nullable=False)
    warnings = Column(JSONB, nullable=False, default=list)
    hazard_alert_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    trigger_reason = Column(String, nullable=False, default="initial")
    superseded = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
