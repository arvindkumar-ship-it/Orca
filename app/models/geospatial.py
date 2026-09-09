"""
ORCA — Geospatial tables.

GENERALIZE of WaveSafe's app/models/geospatial.py:
  beaches      -> marine_zones      (zone_type discriminator added)
  safe_zones   -> safe_harbors
NEW tables (R8 — geofencing):
  maritime_boundaries  (IMBL / EEZ / territorial waters)
  mpa_zones            (Marine Protected Areas / ecologically sensitive zones)

jurisdictions, hospitals, rescue_posts are COPY — reused verbatim from
WaveSafe's app/models/geospatial.py, unchanged, still needed for SOS
escalation routing. Import them from there rather than redefining:
    from app.models.geospatial_wavesafe import Jurisdiction, Hospital, RescuePost

Every Geometry column keeps spatial_index=False — GiST indexes are created
explicitly in the migration SQL (ORCA_MIGRATION.sql), matching WaveSafe's
own documented reason: avoid GeoAlchemy2 auto-creating an index whose name
collides with the migration's explicit index names.
"""
from __future__ import annotations
from sqlalchemy import Column, Text, Boolean, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone

from app.models.base import Base, uuid_pk

# Re-export so COPY files that do `from app.models.geospatial import Beach`
# (their original, correct import path) keep working unchanged — several
# do (app/services/internal_service.py, trip_service.py, admin_service.py,
# app/workers/forecast_worker.py, risk_worker.py — confirmed via repo-wide
# grep during the merge). See geospatial_wavesafe.py for the real definitions.
from app.models.geospatial_wavesafe import Beach, SafeZone, Jurisdiction, Hospital, RescuePost  # noqa: F401


class MarineZone(Base):
    """GENERALIZE of Beach. zone_type distinguishes what R4/R9/R10 treat
    differently: a fishing_zone is scored for PFZ proximity + risk, an
    open_sea_sector is a route-optimizer grid cell's parent region, a
    coastal_beach keeps WaveSafe's original swimmer-safety semantics so
    ORCA can still answer beach-adjacent queries without a second table."""
    __tablename__ = "marine_zones"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    zone_type = Column(Text, nullable=False)  # 'fishing_zone' | 'open_sea_sector' | 'coastal_beach'
    state = Column(Text, nullable=False)
    district = Column(Text)
    coast_region = Column(Text)
    geom = Column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    centroid = Column(Geometry("POINT", srid=4326, spatial_index=False))
    depth_m = Column(Numeric(8, 2))                # relevant for fishing_zone / open_sea_sector, null for coastal_beach
    has_lifeguard = Column(Boolean, default=False)  # meaningful only for coastal_beach, kept for schema parity with WaveSafe
    public_access = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


class SafeHarbor(Base):
    """GENERALIZE of SafeZone. Nearest safe harbor for a vessel to divert to,
    in place of WaveSafe's nearest-lifeguard-post-on-land concept. Same
    shape/mechanism (elevation_m kept for schema parity though not
    meaningful at sea; route_notes now typically holds berthing/fuel info)."""
    __tablename__ = "safe_harbors"
    id = uuid_pk()
    marine_zone_id = Column(UUID(as_uuid=True), ForeignKey("marine_zones.id", ondelete="SET NULL"))
    name = Column(Text, nullable=False)
    geom = Column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    elevation_m = Column(Numeric(8, 2))
    berthing_capacity = Column(Integer)
    has_fuel = Column(Boolean, default=False)
    route_notes = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MaritimeBoundary(Base):
    """NEW — IMBL (International Maritime Boundary Line), EEZ, and
    territorial-waters lines. boundary_type discriminates which regulatory
    regime a ST_DWithin proximity check is evaluating against (R8)."""
    __tablename__ = "maritime_boundaries"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    boundary_type = Column(Text, nullable=False)  # 'IMBL' | 'EEZ' | 'territorial_waters'
    neighboring_country = Column(Text)             # populated for IMBL segments, null otherwise
    geom = Column(Geometry("MULTILINESTRING", srid=4326, spatial_index=False), nullable=False)
    source_authority = Column(Text)                 # e.g. "Ministry of External Affairs", for audit/citation in explanations
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MpaZone(Base):
    """NEW — Marine Protected Areas / ecologically sensitive zones.
    restriction_level drives geofence_service.py's alert severity: a
    no-entry breach is a hard-override in the risk verdict (mirrors
    risk_engine/scoring.py's hard-override alert types), seasonal/advisory
    are soft warnings."""
    __tablename__ = "mpa_zones"
    id = uuid_pk()
    name = Column(Text, nullable=False)
    restriction_level = Column(Text, nullable=False)  # 'no_entry' | 'seasonal' | 'advisory'
    season_start_month = Column(Integer)    # 1-12, null when not seasonal
    season_end_month = Column(Integer)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False)
    governing_body = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
