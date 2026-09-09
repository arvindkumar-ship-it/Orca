"""Module 2B — Geospatial tables. Matches exact SQL: beaches, safe_zones,
jurisdictions, hospitals, rescue_posts.

spatial_index=False on every Geometry column — GiST indexes are created
explicitly in migrations/001_extensions_and_tables.sql instead (same fix
your screenshot already applied, to avoid GeoAlchemy2 auto-creating a spatial
index whose name collides with the doc's exact index names)."""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone

from .base import Base, uuid_pk


class Beach(Base):
    __tablename__ = "beaches"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    district = Column(Text)
    coast_region = Column(Text)
    geom = Column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    centroid = Column(Geometry("POINT", srid=4326, spatial_index=False))
    has_lifeguard = Column(Boolean, default=False)
    public_access = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


class SafeZone(Base):
    __tablename__ = "safe_zones"
    id = uuid_pk()
    beach_id = Column(UUID(as_uuid=True), ForeignKey("beaches.id", ondelete="SET NULL"))
    name = Column(Text, nullable=False)
    geom = Column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    elevation_m = Column(Numeric(8, 2))
    route_notes = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    authority_type = Column(Text, nullable=False)
    contact_phone = Column(Text)
    contact_email = Column(Text)
    service_area_geom = Column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False)
    escalation_level = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Hospital(Base):
    __tablename__ = "hospitals"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    contact_phone = Column(Text)
    contact_email = Column(Text)
    capabilities = Column(JSONB, nullable=False, default=dict)
    capacity_status = Column(Text, default="unknown")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RescuePost(Base):
    __tablename__ = "rescue_posts"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    post_type = Column(Text, nullable=False)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    contact_phone = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
