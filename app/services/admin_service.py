# """Assumes models already exist from earlier modules:
# app.models.hospital.Hospital, app.models.jurisdiction.Jurisdiction,
# app.models.beach.Beach, app.models.safezone.SafeZone,
# app.models.beach_activity_profile.BeachActivityProfile  (Module 1 / 2B / 2C)."""
# import json
# from sqlalchemy import func
# from sqlalchemy.orm import Session

# from app.models.geospatial import Hospital
# from app.models.geospatial import Jurisdiction, Beach
# from app.models.geospatial import SafeZone
# from app.models.forecast_risk import BeachActivityProfile


# def _point(lat: float, lng: float):
#     return func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)


# def _geom_from_geojson(geo):
#     return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geo)), 4326)


# def create_hospital(db: Session, payload) -> Hospital:
#     h = Hospital
#     (
#         name=payload.name, type=payload.type,
#         geom=_point(payload.lat, payload.lng),
#         contact_phone=payload.contact_phone, contact_email=payload.contact_email,
#         capabilities=payload.capabilities, capacity_status=payload.capacity_status,
#     )
#     db.add(h); db.commit(); db.refresh(h)
#     return h


# def create_jurisdiction(db: Session, payload) -> Jurisdiction:
#     j = Jurisdiction(
#         name=payload.name, authority_type=payload.authority_type,
#         contact_phone=payload.contact_phone, contact_email=payload.contact_email,
#         service_area_geom=_geom_from_geojson(payload.service_area_geom_geojson),
#         escalation_level=payload.escalation_level,
#     )
#     db.add(j); db.commit(); db.refresh(j)
#     return j


# def create_beach(db: Session, payload) -> Beach:
#     b = Beach(
#         name=payload.name, state=payload.state, district=payload.district,
#         coast_region=payload.coast_region, geom=_geom_from_geojson(payload.geom_geojson),
#         has_lifeguard=payload.has_lifeguard, public_access=payload.public_access,
#     )
#     db.add(b); db.commit(); db.refresh(b)
#     return b


# def create_threshold(db: Session, payload) -> BeachActivityProfile:
#     t = BeachActivityProfile(
#         beach_id=payload.beach_id, activity_type=payload.activity_type,
#         min_safe_wave_height=payload.min_safe_wave_height,
#         max_safe_current_speed=payload.max_safe_current_speed,
#         max_safe_wind_speed=payload.max_safe_wind_speed,
#         max_safe_swell=payload.max_safe_swell,
#         water_quality_min=payload.water_quality_min,
#         tide_sensitivity=payload.tide_sensitivity,
#         risk_weights=payload.risk_weights,
#     )
#     db.add(t); db.commit(); db.refresh(t)
#     return t


# def create_safezone(db: Session, payload) -> SafeZone:
#     s = SafeZone(
#         beach_id=payload.beach_id, name=payload.name,
#         geom=_geom_from_geojson(payload.geom_geojson),
#         elevation_m=payload.elevation_m, route_notes=payload.route_notes,
#     )
#     db.add(s); db.commit(); db.refresh(s)
#     return s






















"""Assumes models already exist from earlier modules:
app.models.hospital.Hospital, app.models.jurisdiction.Jurisdiction,
app.models.beach.Beach, app.models.safezone.SafeZone,
app.models.beach_activity_profile.BeachActivityProfile  (Module 1 / 2B / 2C)."""
import json
import csv
import io
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.geospatial import Hospital
from app.models.geospatial import Jurisdiction, Beach
from app.models.geospatial import SafeZone
from app.models.forecast_risk import BeachActivityProfile


def _point(lat: float, lng: float):
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)


def _geom_from_geojson(geo):
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geo)), 4326)


def create_hospital(db: Session, payload) -> Hospital:
    h = Hospital(
        name=payload.name, type=payload.type,
        geom=_point(payload.lat, payload.lng),
        contact_phone=payload.contact_phone, contact_email=payload.contact_email,
        capabilities=payload.capabilities, capacity_status=payload.capacity_status,
    )
    db.add(h); db.commit(); db.refresh(h)
    return h


def create_jurisdiction(db: Session, payload) -> Jurisdiction:
    j = Jurisdiction(
        name=payload.name, authority_type=payload.authority_type,
        contact_phone=payload.contact_phone, contact_email=payload.contact_email,
        service_area_geom=_geom_from_geojson(payload.service_area_geom_geojson),
        escalation_level=payload.escalation_level,
    )
    db.add(j); db.commit(); db.refresh(j)
    return j


def create_beach(db: Session, payload) -> Beach:
    b = Beach(
        name=payload.name, state=payload.state, district=payload.district,
        coast_region=payload.coast_region, geom=_geom_from_geojson(payload.geom_geojson),
        has_lifeguard=payload.has_lifeguard, public_access=payload.public_access,
    )
    db.add(b); db.commit(); db.refresh(b)
    return b


def create_threshold(db: Session, payload) -> BeachActivityProfile:
    t = BeachActivityProfile(
        beach_id=payload.beach_id, activity_type=payload.activity_type,
        min_safe_wave_height=payload.min_safe_wave_height,
        max_safe_current_speed=payload.max_safe_current_speed,
        max_safe_wind_speed=payload.max_safe_wind_speed,
        max_safe_swell=payload.max_safe_swell,
        water_quality_min=payload.water_quality_min,
        tide_sensitivity=payload.tide_sensitivity,
        risk_weights=payload.risk_weights,
    )
    db.add(t); db.commit(); db.refresh(t)
    return t


def create_safezone(db: Session, payload) -> SafeZone:
    s = SafeZone(
        beach_id=payload.beach_id, name=payload.name,
        geom=_geom_from_geojson(payload.geom_geojson),
        elevation_m=payload.elevation_m, route_notes=payload.route_notes,
    )
    db.add(s); db.commit(); db.refresh(s)
    return s
# def upsert_beach(db: Session, admin, payload) -> Beach:
#     return create_beach(db, payload)


# def upsert_activity_threshold(db: Session, admin, payload) -> BeachActivityProfile:
#     return create_threshold(db, payload)


# def upsert_jurisdiction(db: Session, admin, payload) -> Jurisdiction:
#     return create_jurisdiction(db, payload)


# def upsert_hospital(db: Session, admin, payload) -> Hospital:
#     return create_hospital(db, payload)

def upsert_beach(db: Session, admin, payload) -> dict:
    b = create_beach(db, payload)
    return {
        "id": str(b.id), "name": b.name, "state": b.state,
        "district": b.district, "coast_region": b.coast_region,
        "has_lifeguard": b.has_lifeguard, "public_access": b.public_access,
    }


def upsert_activity_threshold(db: Session, admin, payload) -> BeachActivityProfile:
    return create_threshold(db, payload)


def upsert_jurisdiction(db: Session, admin, payload) -> dict:
    j = create_jurisdiction(db, payload)
    return {
        "id": str(j.id), "name": j.name, "authority_type": j.authority_type,
        "contact_phone": j.contact_phone, "contact_email": j.contact_email,
        "escalation_level": j.escalation_level,
    }


def upsert_hospital(db: Session, admin, payload) -> dict:
    h = create_hospital(db, payload)
    return {
        "id": str(h.id), "name": h.name, "type": h.type,
        "contact_phone": h.contact_phone, "contact_email": h.contact_email,
        "capabilities": h.capabilities, "capacity_status": h.capacity_status,
    }


def upsert_safezone(db: Session, admin, payload) -> dict:
    s = create_safezone(db, payload)
    return {
        "id": str(s.id), "beach_id": str(s.beach_id), "name": s.name,
        "elevation_m": s.elevation_m, "route_notes": s.route_notes,
    }
def validate_beach_geometry(db: Session, beach_id: str) -> dict:
    row = db.execute(
        text(
            """SELECT
                   ST_IsValid(geom) AS is_valid,
                   ST_IsValidReason(geom) AS invalid_reason,
                   ST_Area(geom::geography) AS area_m2,
                   ST_NPoints(geom) AS point_count,
                   centroid IS NOT NULL AS has_centroid
               FROM beaches WHERE id = :id"""
        ),
        {"id": beach_id},
    ).mappings().first()

    if row is None:
        raise ValueError("beach not found")

    return {
        "beach_id": beach_id,
        "is_valid": row["is_valid"],
        "invalid_reason": row["invalid_reason"] if not row["is_valid"] else None,
        "area_m2": float(row["area_m2"]) if row["area_m2"] is not None else None,
        "point_count": row["point_count"],
        "has_centroid": row["has_centroid"],
    }

# Step 6: incident review list (admin console) — real paginated query against incident_reports.
def list_incidents(db: Session, filters) -> dict:
    where = ["1=1"]
    params = {"limit": filters.page_size, "offset": (filters.page - 1) * filters.page_size}

    if filters.status:
        where.append("status = :status")
        params["status"] = filters.status
    if filters.incident_type:
        where.append("incident_type = :incident_type")
        params["incident_type"] = filters.incident_type
    if filters.beach_id:
        where.append("beach_id = :beach_id")
        params["beach_id"] = filters.beach_id
    if filters.from_:
        where.append("created_at >= :from_")
        params["from_"] = filters.from_
    if filters.to:
        where.append("created_at <= :to")
        params["to"] = filters.to

    where_sql = " AND ".join(where)

    total = db.execute(
        text(f"SELECT count(*) FROM incident_reports WHERE {where_sql}"), params
    ).scalar_one()

    rows = db.execute(
        text(
            f"""SELECT id, user_id, beach_id, incident_type, severity, status,
                       trigger_type, created_at, updated_at
                FROM incident_reports
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset"""
        ),
        params,
    ).mappings().all()

    return {
        "page": filters.page,
        "page_size": filters.page_size,
        "total": total,
        "items": [
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "beach_id": str(r["beach_id"]) if r["beach_id"] else None,
                "incident_type": r["incident_type"],
                "severity": r["severity"],
                "status": r["status"],
                "trigger_type": r["trigger_type"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
    }


# Step 7: acknowledgement review — real query against incident_routes for one incident.
def list_acknowledgements(db: Session, incident_id: str) -> list:
    rows = db.execute(
        text(
            """SELECT id, target_type, target_name, target_id, route_rank,
                      routed_at, ack_status, ack_time, external_ref, last_error
               FROM incident_routes
               WHERE incident_report_id = :incident_id
               ORDER BY route_rank ASC"""
        ),
        {"incident_id": incident_id},
    ).mappings().all()

    return [
        {
            "id": str(r["id"]),
            "target_type": r["target_type"],
            "target_name": r["target_name"],
            "target_id": str(r["target_id"]) if r["target_id"] else None,
            "route_rank": r["route_rank"],
            "routed_at": r["routed_at"].isoformat() if r["routed_at"] else None,
            "ack_status": r["ack_status"],
            "ack_time": r["ack_time"].isoformat() if r["ack_time"] else None,
            "external_ref": r["external_ref"],
            "last_error": r["last_error"],
        }
        for r in rows
    ]


# Step 8: response latency, broken down by target_type (authority/hospital/112) —
# complements the overall mean already served by /v1/admin/analytics/response-time.
def get_response_latency_metrics(db: Session, window_days: int) -> dict:
    rows = db.execute(
        text(
            """SELECT target_type,
                      EXTRACT(EPOCH FROM (ack_time - routed_at)) AS response_s
               FROM incident_routes
               WHERE routed_at >= now() - (:days || ' days')::interval
                 AND ack_time IS NOT NULL"""
        ),
        {"days": window_days},
    ).mappings().all()

    by_type: dict[str, list[float]] = {}
    for r in rows:
        by_type.setdefault(r["target_type"], []).append(float(r["response_s"]))

    breakdown = {
        target_type: {
            "mean_response_time_s": sum(values) / len(values),
            "sample_size": len(values),
        }
        for target_type, values in by_type.items()
    }

    return {"window_days": window_days, "by_target_type": breakdown}


# Step 9: risk rule tuning.
# NOTE: no `risk_rules` table exists in this codebase — risk_engine/scoring.py uses
# hardcoded DEFAULT_WEIGHTS, not a DB-driven ruleset. This function does NOT invent a fake
# rules table. It honestly records the tuning REQUEST as a real audit_events row so admins
# have a paper trail. It does NOT and CANNOT change live risk-scoring behavior.
def update_risk_rule(db: Session, admin, body) -> dict:
    row_id = db.execute(
        text(
            """INSERT INTO audit_events (event_type, entity_type, actor_type, actor_id, payload)
               VALUES ('risk_rule_tune_requested', 'risk_rule', 'admin', :actor_id, :payload)
               RETURNING id"""
        ),
        {
            "actor_id": str(getattr(admin, "id", admin)),
            "payload": json.dumps({
                "rule_id": body.rule_id,
                "parameter": body.parameter,
                "new_value": body.new_value,
                "reason": body.reason,
            }),
        },
    ).scalar_one()
    db.commit()

    return {
        "audit_event_id": str(row_id),
        "status": "logged_not_applied",
        "note": "No risk_rules table exists in this codebase; the request was recorded in "
                "audit_events for review but does not change live scoring weights "
                "(risk_engine/scoring.py uses hardcoded DEFAULT_WEIGHTS).",
    }


# Step 10: log export — real query against one of the 3 permitted tables, serialized as
# CSV or JSON. Empty result sets export as an empty CSV/JSON, not an error.
def export_logs(db: Session, admin, body) -> str:
    table_map = {
        "audit_events": ("audit_events", "created_at"),
        "incident_reports": ("incident_reports", "created_at"),
        "notification_queue": ("notification_queue", "scheduled_for"),
    }
    table_name, time_col = table_map[body.entity_type]

    rows = db.execute(
        text(
            f"""SELECT * FROM {table_name}
                WHERE {time_col} >= :from_ AND {time_col} <= :to
                ORDER BY {time_col} DESC"""
        ),
        {"from_": body.from_, "to": body.to},
    ).mappings().all()

    records = [
        {k: (str(v) if not isinstance(v, (int, float, bool, type(None))) else v)
         for k, v in dict(r).items()}
        for r in rows
    ]

    if body.format == "json":
        return json.dumps(records, default=str)

    output = io.StringIO()
    if records:
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    return output.getvalue()