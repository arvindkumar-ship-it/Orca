# """Module 21 dependency — matches Module 2D SQL exactly."""
# from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, func
# from sqlalchemy.dialects.postgresql import UUID, JSONB
# from sqlalchemy.orm import relationship

# from app.core.db import Base


# class IncidentStatus:
#     CREATED = "created"
#     VALIDATED = "validated"
#     LOCATION_LOCKED = "location_locked"
#     PACKED = "packed"
#     DISPATCHED = "dispatched"
#     ACKNOWLEDGED = "acknowledged"
#     ROUTED = "routed"
#     EN_ROUTE = "en_route"
#     HOSPITAL_NOTIFIED = "hospital_notified"
#     SAFE_ZONE_SHARED = "safe_zone_shared"
#     RESOLVED = "resolved"
#     CLOSED = "closed"
#     ESCALATED = "escalated"


# class IncidentReport(Base):
#     __tablename__ = "incident_reports"

#     id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
#     user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
#     beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="SET NULL"))
#     incident_type = Column(String, nullable=False)
#     severity = Column(String, nullable=False)
#     lat = Column(Numeric(10, 7), nullable=False)
#     lng = Column(Numeric(10, 7), nullable=False)
#     description = Column(String)
#     media = Column(JSONB, nullable=False, server_default="[]")
#     status = Column(String, nullable=False, server_default=IncidentStatus.CREATED)
#     trigger_type = Column(String, nullable=False)
#     battery_pct = Column(Integer)
#     signal_strength = Column(String)
#     current_hazard_context = Column(JSONB, nullable=False, server_default="{}")
#     created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

#     routes = relationship("IncidentRoute", back_populates="incident", cascade="all, delete-orphan")
#     history = relationship("IncidentStatusHistory", back_populates="incident",
#                             cascade="all, delete-orphan", order_by="IncidentStatusHistory.changed_at")


# class IncidentRoute(Base):
#     __tablename__ = "incident_routes"

#     id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
#     incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"),
#                                  nullable=False, index=True)
#     target_type = Column(String, nullable=False)      # 112 | authority | hospital | contact
#     target_name = Column(String, nullable=False)
#     target_id = Column(UUID(as_uuid=True))
#     jurisdiction_id = Column(UUID(as_uuid=True), ForeignKey("jurisdictions.id"))
#     route_rank = Column(Integer, nullable=False)
#     routed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
#     ack_status = Column(String, nullable=False, server_default="sent")
#     ack_time = Column(DateTime(timezone=True))
#     external_ref = Column(String)
#     last_error = Column(String)

#     incident = relationship("IncidentReport", back_populates="routes")


# class IncidentStatusHistory(Base):
#     __tablename__ = "incident_status_history"

#     id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
#     incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"),
#                                  nullable=False, index=True)
#     from_status = Column(String)
#     to_status = Column(String, nullable=False)
#     reason = Column(String)
#     changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

#     incident = relationship("IncidentReport", back_populates="history")









"""Module 2D — Incident, notification & audit tables. Matches exact SQL:
incident_reports, incident_routes, incident_status_history, notification_queue,
audit_events, user_contacts, offline_sync_queue.

B6 fix: IncidentStatus class (from Module 21's incident.py) merged in here — that file's
IncidentReport/IncidentRoute/IncidentStatusHistory classes were discarded because they
lack the `geom` generated column and use the wrong Base import; only this constants class
was worth keeping.
"""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Numeric, Integer, DateTime, ForeignKey, Index, Computed
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone

from .base import Base, uuid_pk


class IncidentStatus:
    CREATED = "created"
    VALIDATED = "validated"
    LOCATION_LOCKED = "location_locked"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    ROUTED = "routed"
    EN_ROUTE = "en_route"
    HOSPITAL_NOTIFIED = "hospital_notified"
    SAFE_ZONE_SHARED = "safe_zone_shared"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class IncidentReport(Base):
    __tablename__ = "incident_reports"
    __table_args__ = (Index("idx_incidents_status", "status"),)
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="SET NULL"))
    activity_type = Column(Text)
    incident_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    lat = Column(Numeric(10, 7), nullable=False)
    lng = Column(Numeric(10, 7), nullable=False)
    # generated column — matches exact SQL's `GENERATED ALWAYS AS (...) STORED`.
    # SQLAlchemy issues this DDL correctly; app code must never write to `geom` directly.
    geom = Column(Geometry("POINT", srid=4326, spatial_index=False),
                  Computed("ST_SetSRID(ST_MakePoint(lng, lat), 4326)", persisted=True))
    description = Column(Text)
    media = Column(JSONB, nullable=False, default=list)
    status = Column(Text, nullable=False, default=IncidentStatus.CREATED)
    trigger_type = Column(Text, nullable=False)
    battery_pct = Column(Integer)
    signal_strength = Column(Text)
    current_hazard_context = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))
    client_incident_id = Column(Text, nullable=True)
    routes = relationship("IncidentRoute", back_populates="incident", cascade="all, delete-orphan",
                          order_by="IncidentRoute.route_rank")


class IncidentRoute(Base):
    __tablename__ = "incident_routes"
    id = uuid_pk()
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    target_type = Column(Text, nullable=False)
    target_name = Column(Text, nullable=False)
    target_id = Column(UUID(as_uuid=True))
    jurisdiction_id = Column(UUID(as_uuid=True), ForeignKey("jurisdictions.id"))
    route_rank = Column(Integer, nullable=False)
    routed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ack_status = Column(Text, nullable=False, default="sent")
    ack_time = Column(DateTime(timezone=True))
    external_ref = Column(Text)
    last_error = Column(Text)
    incident = relationship("IncidentReport", back_populates="routes")



class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"
    id = uuid_pk()
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="CASCADE"),
                                 nullable=False)
    from_status = Column(Text)
    to_status = Column(Text, nullable=False)
    reason = Column(Text)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


# class NotificationQueue(Base):
#     __tablename__ = "notification_queue"
#     __table_args__ = (Index("idx_notification_queue_status", "status", "scheduled_for"),)
#     id = uuid_pk()
#     user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
#     incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="SET NULL"))
#     type = Column(Text, nullable=False)
#     priority = Column(Text, nullable=False)
#     title = Column(Text, nullable=False)
#     body = Column(Text, nullable=False)
#     channel = Column(Text, nullable=False)
#     status = Column(Text, nullable=False, default="queued")
#     scheduled_for = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
#     sent_at = Column(DateTime(timezone=True))
#     delivery_meta = Column(JSONB, nullable=False, default=dict)

class NotificationQueue(Base):
    __tablename__ = "notification_queue"
    __table_args__ = (Index("idx_notification_queue_status", "status", "scheduled_for"),)
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    incident_report_id = Column(UUID(as_uuid=True), ForeignKey("incident_reports.id", ondelete="SET NULL"))
    type = Column(Text, nullable=False)
    priority = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    locale = Column(Text, nullable=False, default="en")
    full_screen = Column(Boolean, nullable=False, default=False)
    status = Column(Text, nullable=False, default="queued")
    scheduled_for = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True))
    delivery_meta = Column(JSONB, nullable=False, default=dict)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("idx_audit_events_entity", "entity_type", "entity_id"),)
    id = uuid_pk()
    event_type = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    actor_type = Column(Text, nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class UserContact(Base):
    __tablename__ = "user_contacts"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    relation = Column(Text)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class OfflineSyncQueue(Base):
    __tablename__ = "offline_sync_queue"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    action_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(Text, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))