"""Module 22 dependency. emergency_contacts already exists (Module 2A); this adds only the
session/target tables needed to persist live-share state, following the same schema conventions."""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class ShareStatus:
    ACTIVE = "active"
    STOPPED = "stopped"


class EmergencyShareSession(Base):
    __tablename__ = "emergency_share_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    share_live_location = Column(Boolean, nullable=False, server_default="true")
    share_route = Column(Boolean, nullable=False, server_default="true")
    status = Column(String, nullable=False, server_default=ShareStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    stopped_at = Column(DateTime(timezone=True))

    targets = relationship("EmergencyShareTarget", back_populates="session", cascade="all, delete-orphan")


class EmergencyShareTarget(Base):
    __tablename__ = "emergency_share_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    share_session_id = Column(UUID(as_uuid=True), ForeignKey("emergency_share_sessions.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("emergency_contacts.id"), nullable=False)
    status = Column(String, nullable=False, server_default="sent")  # sent|failed
    last_error = Column(String)

    session = relationship("EmergencyShareSession", back_populates="targets")
