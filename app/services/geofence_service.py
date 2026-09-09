"""
ORCA — Geofence service (R8: IMBL / restricted waters / MPA / ecologically
sensitive zone notifications).

NEW file. Reuses WaveSafe's exact geofencing mechanism — GiST-indexed
ST_Contains (point-in-polygon) for "am I inside an MPA" and ST_DWithin
(proximity) for "am I approaching the IMBL/EEZ within N km" — the same
PostGIS functions safezone_service.py already relies on for hazard-route
intersection. No new geofencing approach is invented here.

Called by: app/api/v1/geofence.py (thin router), agents/geo_risk_agent.py
(tool-calling wrapper), risk_engine/engine.py (hard-override check for
mpa no_entry breaches, mirroring the tsunami_warning/storm_surge_warning
hard-override pattern already in risk_engine/scoring.py).
Depends on: app.core.db.get_session, marine_zones/maritime_boundaries/
mpa_zones tables (021_orca_geospatial.sql).
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

# Proximity threshold for an IMBL/EEZ "approaching boundary" warning.
# Kept as a module constant (not a magic number in the query) so the
# route_optimizer's edge-cost function and the chat agent's explanation
# text can both reference the same figure without drifting apart.
BOUNDARY_PROXIMITY_WARNING_KM = 5.0
BOUNDARY_PROXIMITY_CRITICAL_KM = 1.0


def check_point(db: Session, lat: float, lng: float, check_time: datetime | None = None) -> dict:
    """
    Single point-in-time geofence check for a vessel's current or planned
    position. Returns a structured verdict — {data, explanation-ready
    fields} — matching the {data, explanation, sources} shape every ORCA
    agent tool call must return (Section 2 of the build spec).
    """
    check_time = check_time or datetime.now(timezone.utc)

    mpa_hit = _mpa_containment(db, lat, lng, check_time)
    boundary = _nearest_boundary(db, lat, lng)

    verdict = "clear"
    if mpa_hit and mpa_hit["restriction_level"] == "no_entry":
        verdict = "breach_no_entry"
    elif mpa_hit and mpa_hit["restriction_level"] in ("seasonal", "advisory"):
        verdict = "advisory_zone"
    elif boundary and boundary["distance_km"] <= BOUNDARY_PROXIMITY_CRITICAL_KM:
        verdict = "boundary_critical"
    elif boundary and boundary["distance_km"] <= BOUNDARY_PROXIMITY_WARNING_KM:
        verdict = "boundary_warning"

    return {
        "verdict": verdict,
        "inside_mpa": mpa_hit is not None,
        "mpa_zone": mpa_hit,
        "nearest_boundary_km": boundary["distance_km"] if boundary else None,
        "boundary_name": boundary["name"] if boundary else None,
        "boundary_type": boundary["boundary_type"] if boundary else None,
        "checked_at": check_time.isoformat(),
    }


def check_route(db: Session, route_wkt: str) -> dict:
    """
    Route-level geofence check — used by route_optimizer/advisory.py and
    the Route agent to flag an entire planned path, not just a single
    point. Returns every MPA the route intersects and the closest approach
    to any maritime boundary along the whole line.
    """
    mpa_rows = db.execute(text("""
        SELECT id, name, restriction_level, governing_body
        FROM mpa_zones
        WHERE active = true
          AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(:wkt), 4326))
    """), {"wkt": route_wkt}).mappings().all()

    boundary_row = db.execute(text("""
        SELECT name, boundary_type,
               ST_Distance(geom::geography, ST_SetSRID(ST_GeomFromText(:wkt),4326)::geography) / 1000.0 AS distance_km
        FROM maritime_boundaries
        WHERE active = true
        ORDER BY distance_km ASC LIMIT 1
    """), {"wkt": route_wkt}).mappings().first()

    intersected = [dict(r) for r in mpa_rows]
    no_entry_hits = [r for r in intersected if r["restriction_level"] == "no_entry"]

    return {
        "route_clear": not no_entry_hits and (not boundary_row or boundary_row["distance_km"] > BOUNDARY_PROXIMITY_CRITICAL_KM),
        "mpa_intersections": intersected,
        "no_entry_violations": no_entry_hits,
        "closest_boundary_km": float(boundary_row["distance_km"]) if boundary_row else None,
        "closest_boundary_name": boundary_row["name"] if boundary_row else None,
    }


def _mpa_containment(db: Session, lat: float, lng: float, check_time: datetime) -> dict | None:
    month = check_time.month
    row = db.execute(text("""
        SELECT id, name, restriction_level, governing_body, season_start_month, season_end_month
        FROM mpa_zones
        WHERE active = true
          AND ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
        ORDER BY
            CASE restriction_level WHEN 'no_entry' THEN 0 WHEN 'seasonal' THEN 1 ELSE 2 END
        LIMIT 1
    """), {"lat": lat, "lng": lng}).mappings().first()

    if row is None:
        return None

    result = dict(row)
    # A seasonal MPA only restricts during its declared window (R8: "seasonal"
    # restriction_level is meaningless without this check — being inside the
    # polygon in the off-season is not a breach).
    if result["restriction_level"] == "seasonal":
        start, end = result["season_start_month"], result["season_end_month"]
        in_season = (
            (start <= end and start <= month <= end) or
            (start > end and (month >= start or month <= end))  # wraps across year boundary, e.g. Nov-Feb
        )
        if not in_season:
            return None
    return {k: v for k, v in result.items() if k not in ("season_start_month", "season_end_month")}


def _nearest_boundary(db: Session, lat: float, lng: float) -> dict | None:
    row = db.execute(text("""
        SELECT name, boundary_type,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) / 1000.0 AS distance_km
        FROM maritime_boundaries
        WHERE active = true
        ORDER BY distance_km ASC LIMIT 1
    """), {"lat": lat, "lng": lng}).mappings().first()
    if row is None:
        return None
    result = dict(row)
    result["distance_km"] = round(float(result["distance_km"]), 3)
    return result
