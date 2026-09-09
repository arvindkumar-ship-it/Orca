"""Module 1 — one-time data loader: GeoJSON -> spatial tables.
ASSUMPTION: app.models/app.db as in Module 2. Run manually per data file,
not a running service.

Usage:
    python -m scripts.load_geojson beaches path/to/beaches.geojson
    python -m scripts.load_geojson safe_zones path/to/safe_zones.geojson
    python -m scripts.load_geojson jurisdictions path/to/jurisdictions.geojson
    python -m scripts.load_geojson hospitals path/to/hospitals.geojson
    python -m scripts.load_geojson rescue_posts path/to/rescue_posts.geojson
"""
from __future__ import annotations
import json
import sys

from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_SetSRID
from app.core.db import get_session
from app.models import (               # ASSUMPTION
    Beach, SafeZone, Jurisdiction, Hospital, RescuePost,
)

TABLE_MODEL = {
    "beaches": Beach, "safe_zones": SafeZone, "jurisdictions": Jurisdiction,
    "hospitals": Hospital, "rescue_posts": RescuePost,
}

# Per-table geometry column name (jurisdictions uses service_area_geom, others use geom)
GEOM_COLUMN = {"jurisdictions": "service_area_geom"}

# Per-table field mapping: GeoJSON `properties` key -> ORM column name.
# Extend as needed — unmapped properties are ignored, not guessed into a column.
FIELD_MAP = {
    "beaches": {"name": "name", "state": "state", "district": "district",
                "coast_region": "coast_region", "has_lifeguard": "has_lifeguard"},
    "safe_zones": {"name": "name", "beach_id": "beach_id", "elevation_m": "elevation_m",
                   "route_notes": "route_notes"},
    "jurisdictions": {"name": "name", "authority_type": "authority_type",
                      "contact_phone": "contact_phone", "contact_email": "contact_email",
                      "escalation_level": "escalation_level"},
    "hospitals": {"name": "name", "type": "type", "contact_phone": "contact_phone",
                 "contact_email": "contact_email", "capabilities": "capabilities",
                 "capacity_status": "capacity_status"},
    "rescue_posts": {"name": "name", "post_type": "post_type", "contact_phone": "contact_phone"},
}


def load_geojson(table_name: str, path: str) -> int:
    if table_name not in TABLE_MODEL:
        raise ValueError(f"unknown table '{table_name}', must be one of {list(TABLE_MODEL)}")

    model = TABLE_MODEL[table_name]
    geom_col = GEOM_COLUMN.get(table_name, "geom")
    field_map = FIELD_MAP[table_name]

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    with get_session() as session:
        for feature in data["features"]:
            props = feature.get("properties", {})
            kwargs = {orm_col: props[gj_key] for gj_key, orm_col in field_map.items() if gj_key in props}
            kwargs[geom_col] = ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(feature["geometry"])), 4326)
            session.add(model(**kwargs))
            count += 1
        session.commit()
    return count


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m scripts.load_geojson <table_name> <path.geojson>")
        sys.exit(1)
    n = load_geojson(sys.argv[1], sys.argv[2])
    print(f"loaded {n} rows into {sys.argv[1]}")
