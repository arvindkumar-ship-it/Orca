"""Module 2A — Core master tables. Matches exact SQL: users, user_devices,
emergency_contacts."""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

from .base import Base, uuid_pk


class User(Base):
    __tablename__ = "users"
    id = uuid_pk()
    phone = Column(Text, unique=True)
    email = Column(Text, unique=True)
    role = Column(Text, nullable=False, default="user")
    name = Column(Text)
    preferred_language = Column(Text, default="en")
    consent_location = Column(Boolean, default=False)
    consent_emergency_share = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

class UserDevice(Base):
    __tablename__ = "user_devices"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(Text, nullable=False)
    device_token = Column(Text, nullable=False)
    push_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    relation = Column(Text)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
