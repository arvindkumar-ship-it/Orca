"""
ORCA — ingestion/orca_persistence.py (NEW)

GENERALIZE-shaped companion to ingestion/persistence.py (COPY, unchanged for
hazard/forecast events). Handles the two new record types this project adds:
PFZ_ADVISORY -> pfz_advisories, SST_RASTER/CHLOROPHYLL_RASTER ->
raster_products. Same pattern as the original: build the ORM row from the
already-validated RawIngestRecord, commit, publish a Redis event so
downstream consumers (Ocean Analytics agent's cache, route_optimizer's
watcher) know new data landed — mirrors persistence.py's
RISK_RECOMPUTE_CHANNEL pub/sub exactly, just a different channel name.
"""
from __future__ import annotations
import json
import logging

import redis
from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_SetSRID

from app.core.db import get_session
from app.models.ocean_products import PfzAdvisory, RasterProduct
from ingestion.schemas import RawIngestRecord, RecordType

logger = logging.getLogger("ingestion.orca_persistence")

OCEAN_PRODUCT_UPDATE_CHANNEL = "ocean_products:updated"


def persist_pfz_advisory(record: RawIngestRecord, redis_client: redis.Redis) -> str:
    if record.type != RecordType.PFZ_ADVISORY:
        raise ValueError(f"persist_pfz_advisory called with wrong record type: {record.type}")
    pf = record.parsed_fields
    with get_session() as session:
        row = PfzAdvisory(
            landing_center_id=pf.get("landing_center_id"),
            landing_center_name=pf.get("landing_center_name"),
            state=pf.get("state"),
            advisory_date=record.start_time,
            geom=ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(record.geometry.model_dump())), 4326),
            distance_from_coast_km=pf.get("distance_from_coast_km"),
            bearing_deg=pf.get("bearing_deg"),
            depth_m=pf.get("depth_m"),
            sst_celsius=pf.get("sst_celsius"),
            chlorophyll_mg_m3=pf.get("chlorophyll_mg_m3"),
            source_confidence=record.source_confidence,
            raw_payload=record.raw_json,
        )
        session.add(row)
        session.flush()
        row_id = str(row.id)
        session.commit()

    redis_client.publish(OCEAN_PRODUCT_UPDATE_CHANNEL, json.dumps({"type": "pfz_advisory", "id": row_id}))
    logger.info("orca_persistence.pfz_advisory_stored id=%s landing_center=%s", row_id, pf.get("landing_center_id"))
    return row_id


def persist_raster_product(record: RawIngestRecord, redis_client: redis.Redis) -> str:
    if record.type not in (RecordType.SST_RASTER, RecordType.CHLOROPHYLL_RASTER):
        raise ValueError(f"persist_raster_product called with wrong record type: {record.type}")
    pf = record.parsed_fields
    with get_session() as session:
        row = RasterProduct(
            product=pf.get("product"),
            tile_id=pf.get("tile_id"),
            product_time=record.start_time,
            footprint=ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(record.geometry.model_dump())), 4326),
            mean_value=pf.get("mean_value"),
            min_value=pf.get("min_value"),
            max_value=pf.get("max_value"),
            unit=pf.get("unit"),
            raster_url=pf.get("raster_url"),
            cloud_cover_pct=pf.get("cloud_cover_pct"),
            source_confidence=record.source_confidence,
        )
        session.add(row)
        session.flush()
        row_id = str(row.id)
        session.commit()

    redis_client.publish(OCEAN_PRODUCT_UPDATE_CHANNEL, json.dumps({"type": pf.get("product"), "id": row_id}))
    logger.info("orca_persistence.raster_product_stored id=%s product=%s tile=%s", row_id, pf.get("product"), pf.get("tile_id"))
    return row_id
