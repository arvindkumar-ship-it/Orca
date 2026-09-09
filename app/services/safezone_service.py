import json
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core import audit

DEFAULT_WEIGHTS = {"theta1": 0.45, "theta2": 0.25, "theta3": 0.15, "theta4": 0.15}
WALK_SPEED_MPS = 1.1
SEARCH_RADIUS_M = 3000


def _severity_weight(sev: str) -> float:
    return {"severe": 1.0, "moderate": 0.6}.get(sev, 0.3)


def _find_candidates(db: Session, lat: float, lng: float, beach_id: str | None) -> list[dict]:
    rows = db.execute(text("""
        SELECT sz.id AS safe_zone_id, sz.name, sz.elevation_m,
               ST_Distance(sz.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m,
               ST_AsText(ST_ShortestLine(ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geometry, sz.geom)) AS route_wkt,
               ST_AsGeoJSON(ST_ShortestLine(ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geometry, sz.geom)) AS route_geojson
        FROM safe_zones sz
        WHERE sz.active = true
          AND (:beach_id IS NULL OR sz.beach_id = :beach_id)
          AND ST_DWithin(sz.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY distance_m ASC LIMIT 8
    """), {"lat": lat, "lng": lng, "beach_id": beach_id, "radius": SEARCH_RADIUS_M}).mappings().all()
    return [dict(r) for r in rows]


def _hazard_exposure(db: Session, route_wkt: str) -> tuple[float, list[str]]:
    rows = db.execute(text("""
        SELECT id, severity FROM hazard_alerts
        WHERE status = 'active' AND (valid_to IS NULL OR valid_to > now())
          AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(:wkt), 4326))
    """), {"wkt": route_wkt}).mappings().all()
    exposure = sum(_severity_weight(r["severity"]) for r in rows)
    return exposure, [str(r["id"]) for r in rows]


def _crowd_risk(db: Session, route_wkt: str) -> float:
    # Proxy for crowding: active trip_plans near the destination beach — no dedicated
    # crowd-density source in schema. Flagged heuristic.
    row = db.execute(text("""
        SELECT count(*)::int AS active_count
        FROM trip_plans tp JOIN beaches b ON b.id = tp.beach_id
        WHERE tp.status = 'active'
          AND ST_DWithin(b.geom::geography, ST_SetSRID(ST_GeomFromText(:wkt),4326)::geography, 300)
    """), {"wkt": route_wkt}).mappings().first()
    return min(row["active_count"] / 50, 1)


def _build_instruction(name: str, eta: float, hazard_types: list[str], exposure: float) -> str:
    if any(t in ("cyclone", "storm_surge") for t in hazard_types):
        return f"Move uphill immediately to {name}. Do not enter the water. Estimated time: {eta} min."
    if exposure > 0:
        return f"Walk to {name} avoiding the marked hazard area. Estimated time: {eta} min. Keep your phone on."
    return f"Walk to {name}. Estimated time: {eta} min. Stay on the marked route and away from the water line."


def _build_warnings(hazard_types: list[str]) -> list[str]:
    warnings = []
    if any(t in ("cyclone", "storm_surge") for t in hazard_types):
        warnings += ["Do not enter water.", "Stay where you are if uphill movement is not immediately safe, and keep your phone on."]
    if not hazard_types:
        warnings.append("Share your live location with your emergency contact.")
    return warnings


def _score_candidate(db: Session, c: dict, weights: dict) -> dict:
    exposure, hazard_ids = _hazard_exposure(db, c["route_wkt"])
    crowd_risk = _crowd_risk(db, c["route_wkt"])
    elevation_gain_m = float(c["elevation_m"] or 0)
    distance_norm = min(float(c["distance_m"]) / SEARCH_RADIUS_M, 1)
    elevation_norm = min(elevation_gain_m / 20, 1)

    score = (weights["theta1"] * min(exposure, 1) + weights["theta2"] * distance_norm +
             weights["theta3"] * elevation_norm + weights["theta4"] * crowd_risk)
    eta_minutes = round((float(c["distance_m"]) / WALK_SPEED_MPS) / 60 + elevation_gain_m * 0.05, 1)

    return {**c, "hazard_exposure": exposure, "crowd_risk": crowd_risk, "elevation_gain_m": elevation_gain_m,
            "route_score": round(score, 5), "eta_minutes": eta_minutes, "hazard_alert_ids": hazard_ids}


def compute_safezone_guidance(db: Session, user_id: str, lat: float, lng: float, beach_id: str | None = None,
                               incident_report_id: str | None = None, trip_plan_id: str | None = None,
                               trigger_reason: str = "initial", weights: dict = DEFAULT_WEIGHTS) -> dict:
    candidates = _find_candidates(db, lat, lng, beach_id)
    if not candidates:
        raise ValueError("NO_SAFE_ZONE_FOUND_IN_RADIUS")

    scored = sorted((_score_candidate(db, c, weights) for c in candidates), key=lambda x: x["route_score"])
    best = scored[0]

    hazard_types = []
    if best["hazard_alert_ids"]:
        rows = db.execute(text("SELECT alert_type FROM hazard_alerts WHERE id = ANY(CAST(:ids AS uuid[]))"),
                           {"ids": best["hazard_alert_ids"]}).mappings().all()
        hazard_types = [r["alert_type"] for r in rows]

    instruction = _build_instruction(best["name"], best["eta_minutes"], hazard_types, best["hazard_exposure"])
    warnings = _build_warnings(hazard_types)

    if incident_report_id:
        db.execute(text("""UPDATE safezone_guidance SET superseded = true
                            WHERE incident_report_id = :irid AND superseded = false"""), {"irid": incident_report_id})
    elif user_id:
        db.execute(text("""UPDATE safezone_guidance SET superseded = true
                            WHERE user_id = :uid AND incident_report_id IS NULL AND superseded = false"""), {"uid": user_id})

    row = db.execute(text("""
        INSERT INTO safezone_guidance
          (user_id, incident_report_id, trip_plan_id, origin_geom, safe_zone_id, route_geom,
           distance_m, elevation_gain_m, hazard_exposure, crowd_risk, route_score, eta_minutes,
           instruction_text, warnings, hazard_alert_ids, trigger_reason)
        VALUES (:uid,:irid,:tpid, ST_SetSRID(ST_MakePoint(:lng,:lat),4326), :szid, ST_SetSRID(ST_GeomFromText(:wkt),4326),
                :dist,:elev,:exp,:crowd,:score,:eta,:instr,:warn,CAST(:hids AS uuid[]),:reason)
        RETURNING id, computed_at
    """), {
        "uid": user_id, "irid": incident_report_id, "tpid": trip_plan_id, "lng": lng, "lat": lat,
        "szid": best["safe_zone_id"], "wkt": best["route_wkt"], "dist": best["distance_m"],
        "elev": best["elevation_gain_m"], "exp": best["hazard_exposure"], "crowd": best["crowd_risk"],
        "score": best["route_score"], "eta": best["eta_minutes"], "instr": instruction,
        "warn": json.dumps(warnings), "hids": best["hazard_alert_ids"], "reason": trigger_reason,
    }).mappings().first()
    db.commit()

    audit.log_audit_event(db, event_type="safezone.guidance.computed", entity_type="safezone_guidance",
                     entity_id=str(row["id"]), actor_type="system" if incident_report_id else "user",
                     actor_id=user_id, payload={"safe_zone_id": best["safe_zone_id"], "route_score": best["route_score"]})

    return {
        "guidance_id": str(row["id"]), "safe_zone_id": str(best["safe_zone_id"]), "safe_zone_name": best["name"],
        "route_geojson": json.loads(best["route_geojson"]), "distance_m": best["distance_m"],
        "eta_minutes": best["eta_minutes"], "route_score": best["route_score"], "instruction": instruction,
        "warnings": warnings, "hazard_alert_ids": best["hazard_alert_ids"], "computed_at": row["computed_at"],
        "trigger_reason": trigger_reason,
    }


def recompute_guidance(db: Session, guidance_id: str, lat: float, lng: float, reason: str) -> dict:
    row = db.execute(text("""SELECT user_id, incident_report_id, trip_plan_id FROM safezone_guidance
                              WHERE id = :id"""), {"id": guidance_id}).mappings().first()
    if not row:
        raise ValueError("GUIDANCE_NOT_FOUND")
    return compute_safezone_guidance(db, str(row["user_id"]) if row["user_id"] else None, lat, lng,
                                      incident_report_id=str(row["incident_report_id"]) if row["incident_report_id"] else None,
                                      trip_plan_id=str(row["trip_plan_id"]) if row["trip_plan_id"] else None,
                                      trigger_reason=reason)


def get_active_guidance(db: Session, user_id: str, incident_report_id: str | None = None) -> dict | None:
    # Bug fix — previously selected safe_zone_id only, no name. incidents.py's get_incident()
    # needs safe_zone["safe_zone_name"] (matches compute_safezone_guidance()'s own return shape).
    # Joined to safe_zones for sz.name.
    row = db.execute(text("""
        SELECT sg.id, sg.safe_zone_id, sz.name AS safe_zone_name,
               ST_AsGeoJSON(sg.route_geom) AS route_geojson, sg.distance_m, sg.eta_minutes,
               sg.route_score, sg.instruction_text, sg.warnings, sg.hazard_alert_ids, sg.computed_at
        FROM safezone_guidance sg
        JOIN safe_zones sz ON sz.id = sg.safe_zone_id
        WHERE sg.superseded = false
          AND (CAST(:irid AS uuid) IS NULL OR sg.incident_report_id = :irid)
          AND (CAST(:irid AS uuid) IS NOT NULL OR sg.user_id = :uid)
        ORDER BY sg.computed_at DESC LIMIT 1
    """), {"irid": incident_report_id, "uid": user_id}).mappings().first()
    if not row:
        return None
    result = dict(row)
    result["route_geojson"] = json.loads(result["route_geojson"])
    return result


def share_guidance(db: Session, guidance_id: str, actor_user_id: str) -> int:
    row = db.execute(text("""
        SELECT sg.user_id, sg.instruction_text, sg.eta_minutes, sg.incident_report_id, sz.name AS safe_zone_name
        FROM safezone_guidance sg JOIN safe_zones sz ON sz.id = sg.safe_zone_id WHERE sg.id = :id
    """), {"id": guidance_id}).mappings().first()
    if not row:
        raise ValueError("GUIDANCE_NOT_FOUND")

    contacts = db.execute(text("""SELECT name, phone FROM emergency_contacts
                                   WHERE user_id = :uid ORDER BY priority ASC"""), {"uid": row["user_id"]}).mappings().all()
    queued = 0
    for c in contacts:
        db.execute(text("""
            INSERT INTO notification_queue (user_id, incident_report_id, type, priority, title, body, channel, status)
            VALUES (:uid,:irid,'safezone_share','high',:title,:body,'sms','queued')
        """), {"uid": row["user_id"], "irid": row["incident_report_id"], "title": "Safe zone route shared",
               "body": f"{row['safe_zone_name']} — {row['instruction_text']} ETA {row['eta_minutes']} min."})
        queued += 1
    db.commit()

    audit.log_audit_event(db, event_type="safezone.guidance.shared", entity_type="safezone_guidance",
                     entity_id=guidance_id, actor_type="user", actor_id=actor_user_id,
                     payload={"contacts_notified": queued})
    return queued
