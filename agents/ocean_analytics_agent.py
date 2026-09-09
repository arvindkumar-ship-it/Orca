"""
ORCA — agents/ocean_analytics_agent.py (NEW)

Answers: "Where is the nearest PFZ today?", "Which regions show high
chlorophyll and favourable SST?" Queries pfz_advisories/raster_products
directly (both populated by ingestion/orca_persistence.py) — no scoring or
business logic here, per the thin-wrapper rule.
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.base import AgentResult, ToolRegistry, ToolSpec

NEAREST_PFZ_RADIUS_M = 200_000  # 200km — PFZ advisories are sparse (586 landing centers nationwide), needs a wide search


def find_nearest_pfz(db: Session, lat: float, lng: float, **_) -> AgentResult:
    rows = db.execute(text("""
        SELECT landing_center_name, state, advisory_date, distance_from_coast_km, bearing_deg, depth_m,
               sst_celsius, chlorophyll_mg_m3, ST_Y(geom) AS lat, ST_X(geom) AS lng,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) / 1000.0 AS distance_km
        FROM pfz_advisories
        WHERE advisory_date >= now() - interval '36 hours'
          AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY distance_km ASC LIMIT 5
    """), {"lat": lat, "lng": lng, "radius": NEAREST_PFZ_RADIUS_M}).mappings().all()

    if not rows:
        return AgentResult(
            data={"pfz_advisories": []},
            explanation=["No recent PFZ advisory found within 200km — either outside coverage or a cloud-affected/ban day."],
            sources=["pfz_advisories (INCOIS)"],
        )
    nearest = rows[0]
    explanation = [
        f"Nearest PFZ advisory: {round(float(nearest['distance_km']), 1)}km away, "
        f"bearing {nearest['bearing_deg']}° at depth {nearest['depth_m']}m "
        f"(SST {nearest['sst_celsius']}°C, chlorophyll {nearest['chlorophyll_mg_m3']}mg/m³)."
    ]
    return AgentResult(data={"pfz_advisories": [dict(r) for r in rows]}, explanation=explanation,
                        sources=["pfz_advisories (INCOIS PFZ advisory, SST+chlorophyll derived)"])


def get_sst_chlorophyll_hotspots(db: Session, min_lat: float, min_lng: float, max_lat: float, max_lng: float,
                                  product: str = "chlorophyll", **_) -> AgentResult:
    if product not in ("sst", "chlorophyll"):
        return AgentResult(data={"error": "product must be 'sst' or 'chlorophyll'"}, explanation=[], sources=[])
    rows = db.execute(text("""
        SELECT tile_id, product_time, mean_value, unit, cloud_cover_pct, ST_AsGeoJSON(footprint) AS footprint
        FROM raster_products
        WHERE product = :product
          AND product_time >= now() - interval '72 hours'
          AND ST_Intersects(footprint, ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326))
        ORDER BY mean_value DESC NULLS LAST, product_time DESC
        LIMIT 20
    """), {"product": product, "min_lat": min_lat, "min_lng": min_lng, "max_lat": max_lat, "max_lng": max_lng}).mappings().all()

    if not rows:
        return AgentResult(data={"tiles": []}, explanation=[f"No recent {product} tiles for this region."],
                            sources=["raster_products (ISRO Bhuvan/MOSDAC)"])
    top = rows[0]
    explanation = [f"Highest {product} tile: {top['mean_value']} {top['unit']} (cloud cover {top['cloud_cover_pct']}%)."]
    return AgentResult(data={"tiles": [dict(r) for r in rows]}, explanation=explanation,
                        sources=["raster_products (ISRO Bhuvan/MOSDAC SST + chlorophyll)"])


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(
        name="ocean_find_nearest_pfz",
        description="Find the nearest Potential Fishing Zone (PFZ) advisory to a lat/lng point, issued in the last 36 hours.",
        input_schema={"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}},
                      "required": ["lat", "lng"]},
        handler=find_nearest_pfz,
    ))
    reg.register(ToolSpec(
        name="ocean_get_sst_chlorophyll_hotspots",
        description="Get SST or chlorophyll hotspot tiles (highest values first) within a bounding box, last 72 hours.",
        input_schema={
            "type": "object",
            "properties": {
                "min_lat": {"type": "number"}, "min_lng": {"type": "number"},
                "max_lat": {"type": "number"}, "max_lng": {"type": "number"},
                "product": {"type": "string", "enum": ["sst", "chlorophyll"], "default": "chlorophyll"},
            },
            "required": ["min_lat", "min_lng", "max_lat", "max_lng"],
        },
        handler=get_sst_chlorophyll_hotspots,
    ))
    return reg
