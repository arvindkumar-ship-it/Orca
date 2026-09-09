import uuid
from sqlalchemy import Column, ForeignKey, String, Integer, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from app.models.base import Base


class LiveTrackingSession(Base):
    __tablename__ = "live_tracking_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=False, default="awaiting_acknowledgment")
    tracking_mode = Column(String, nullable=False, default="critical")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_ping_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    end_reason = Column(String, nullable=True)


class LocationPing(Base):
    __tablename__ = "location_pings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("live_tracking_sessions.id", ondelete="CASCADE"), nullable=False)
    geom = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    accuracy_m = Column(Numeric(8, 2))
    speed_mps = Column(Numeric(8, 3))
    heading = Column(Numeric(6, 2))
    battery_pct = Column(Integer)
    signal_strength = Column(String)
    source = Column(String, nullable=False, default="gps")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
