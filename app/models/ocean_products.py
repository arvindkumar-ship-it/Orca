"""
ORCA — app/models/ocean_products.py (NEW)

Backing tables for the two new/generalized connectors
(ingestion/incois_connector.py -> PfzAdvisory, ingestion/
mosdac_bhuvan_connector.py -> RasterProduct). Not part of WaveSafe's
original schema — WaveSafe's ingestion/persistence.py only ever wrote to
hazard_alerts/beach_forecasts, because OCEAN_FORECAST/HAZARD_WARNING/
LOCAL_CLOSURE were its only record types. PFZ_ADVISORY/SST_RASTER/
CHLOROPHYLL_RASTER (added in ingestion/ORCA_SCHEMA_PATCH.md) need their own
destination tables — this file is that destination.
"""
from __future__ import annotations
from sqlalchemy import Column, Text, Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone

from app.models.base import Base, uuid_pk


class PfzAdvisory(Base):
    __tablename__ = "pfz_advisories"
    __table_args__ = (Index("idx_pfz_advisories_geom_time", "advisory_date"),)
    id = uuid_pk()
    landing_center_id = Column(Text, nullable=False)
    landing_center_name = Column(Text)
    state = Column(Text)
    advisory_date = Column(DateTime(timezone=True), nullable=False)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    distance_from_coast_km = Column(Numeric(8, 2))
    bearing_deg = Column(Numeric(6, 2))
    depth_m = Column(Numeric(8, 2))
    sst_celsius = Column(Numeric(6, 2))
    chlorophyll_mg_m3 = Column(Numeric(8, 3))
    source_confidence = Column(Numeric(4, 3), default=1.0)
    raw_payload = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RasterProduct(Base):
    """SST or chlorophyll satellite tile summary — the tile FOOTPRINT and
    summary stats are stored here; the raster body itself stays at
    raster_url for on-demand fetch (see mosdac_bhuvan_connector.py's
    module docstring for why the raster body isn't downloaded here)."""
    __tablename__ = "raster_products"
    __table_args__ = (Index("idx_raster_products_time", "product_time"),)
    id = uuid_pk()
    product = Column(Text, nullable=False)  # 'sst' | 'chlorophyll'
    tile_id = Column(Text, nullable=False)
    product_time = Column(DateTime(timezone=True), nullable=False)
    footprint = Column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    mean_value = Column(Numeric(10, 4))
    min_value = Column(Numeric(10, 4))
    max_value = Column(Numeric(10, 4))
    unit = Column(Text, nullable=False)
    raster_url = Column(Text)
    cloud_cover_pct = Column(Numeric(5, 2))
    source_confidence = Column(Numeric(4, 3), default=1.0)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
