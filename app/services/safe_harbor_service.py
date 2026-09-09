"""
ORCA — GENERALIZE of app/services/safezone_service.py -> safe harbor guidance.

Same scored-candidate mechanism as the original (find nearby candidates via
ST_DWithin, score by hazard exposure + distance + a secondary factor,
persist to a guidance table, build instruction/warning text). Two changes
from the original beach/land version:
  1. safe_zones/beach_id -> safe_harbors/marine_zone_id.
  2. crowd_risk (a "how many other trip_plans are near this beach" proxy)
     is dropped — meaningless for a vessel diverting to a harbor at sea, and
     WaveSafe's own comment already flags it as a heuristic, not a real
     signal. Its weight is redistributed into hazard_exposure + distance so
     the score still sums to the same total weight of 1.0.
  3. elevation_gain_m dropped — a harbor has no "uphill walk", it's a
     bearing+distance vessel diversion. Replaced with fuel/berthing fitness
     as the operational tie-breaker (has_fuel, berthing_capacity).
"""
import json
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core import audit

DEFAULT_WEIGHTS = {"theta1": 0.55, "theta2": 0.30, "theta3": 0.15}  # hazard, distance, operational_fitness
VESSEL_SPEED_MPS = 4.0  # ~7.8 knots, typical small fishing-vessel cruise speed — override per-vessel via caller
SEARCH_RADIUS_M = 50000  # 50km — open-sea search radius, wider than WaveSafe's 3km beach-walk radius


def _severity_weight(sev: str) -> float:
    return {"severe": 1.0, "moderate": 0.6}.get(sev, 0.3)


def _find_candidates(db: Session, lat: float, lng: float, marine_zone_id: str | None) -> list[dict]:
    rows = db.execute(text("""
        SELECT sh.id AS safe_harbor_id, sh.name, sh.has_fuel, sh.berthing_capacity,
               ST_Distance(sh.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m,
               ST_AsText(ST_ShortestLine(ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geometry, sh.geom)) AS route_wkt,
               ST_AsGeoJSON(ST_ShortestLine(ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geometry, sh.geom)) AS route_geojson
        FROM safe_harbors sh
        WHERE sh.active = true
          AND (:marine_zone_id IS NULL OR sh.marine_zone_id = :marine_zone_id)
          AND ST_DWithin(sh.geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY distance_m ASC LIMIT 8
    """), {"lat": lat, "lng": lng, "marine_zone_id": marine_zone_id, "radius": SEARCH_RADIUS_M}).mappings().all()
    return [dict(r) for r in rows]


def _hazard_exposure(db: Session, route_wkt: str) -> tuple[float, list[str]]:
    rows = db.execute(text("""
        SELECT id, severity FROM hazard_alerts
        WHERE status = 'active' AND (valid_to IS NULL OR valid_to > now())
          AND ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(:wkt), 4326))
    """), {"wkt": route_wkt}).mappings().all()
    exposure = sum(_severity_weight(r["severity"]) for r in rows)
    return exposure, [str(r["id"]) for r in rows]


def _operational_fitness(c: dict) -> float:
    """Lower is better, matching the score's minimize-is-best convention.
    A harbor with fuel and berthing capacity is a worse (higher) score
    contribution only if it LACKS those, i.e. this term penalizes an
    unequipped harbor rather than rewarding an equipped one."""
    penalty = 0.0
    if not c.get("has_fuel"):
        penalty += 0.5
    if not c.get("berthing_capacity"):
        penalty += 0.5
    return penalty


def _build_instruction(name: str, eta: float, hazard_types: list[str], exposure: float) -> str:
    if any(t in ("cyclone", "storm_surge") for t in hazard_types):
        return f"Divert immediately to {name}. Do not remain in open water. Estimated time: {eta} min."
    if exposure > 0:
        return f"Head to {name}, routing around the marked hazard area. Estimated time: {eta} min. Maintain radio contact."
    return f"Nearest safe harbor is {name}. Estimated time: {eta} min."


def _build_warnings(hazard_types: list[str]) -> list[str]:
    warnings = []
    if any(t in ("cyclone", "storm_surge") for t in hazard_types):
        warnings += ["Do not remain in open water.", "Maintain radio/GPS contact with coastal authority."]
    if not hazard_types:
        warnings.append("Share your live position with your emergency contact / harbor authority.")
    return warnings


def _score_candidate(db: Session, c: dict, weights: dict) -> dict:
    exposure, hazard_ids = _hazard_exposure(db, c["route_wkt"])
    fitness_penalty = _operational_fitness(c)
    distance_norm = min(float(c["distance_m"]) / SEARCH_RADIUS_M, 1)

    score = (weights["theta1"] * min(exposure, 1) + weights["theta2"] * distance_norm +
             weights["theta3"] * fitness_penalty)
    eta_minutes = round((float(c["distance_m"]) / VESSEL_SPEED_MPS) / 60, 1)

    return {**c, "hazard_exposure": exposure, "operational_penalty": fitness_penalty,
            "route_score": round(score, 5), "eta_minutes": eta_minutes, "hazard_alert_ids": hazard_ids}


def compute_safe_harbor_guidance(db: Session, user_id: str, lat: float, lng: float,
                                  marine_zone_id: str | None = None, incident_report_id: str | None = None,
                                  trigger_reason: str = "initial", weights: dict = DEFAULT_WEIGHTS) -> dict:
    candidates = _find_candidates(db, lat, lng, marine_zone_id)
    if not candidates:
        raise ValueError("NO_SAFE_HARBOR_FOUND_IN_RADIUS")

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
        db.execute(text("""UPDATE safe_harbor_guidance SET superseded = true
                            WHERE incident_report_id = :irid AND superseded = false"""), {"irid": incident_report_id})
    elif user_id:
        db.execute(text("""UPDATE safe_harbor_guidance SET superseded = true
                            WHERE user_id = :uid AND incident_report_id IS NULL AND superseded = false"""), {"uid": user_id})

    row = db.execute(text("""
        INSERT INTO safe_harbor_guidance
          (user_id, incident_report_id, origin_geom, safe_harbor_id, route_geom,
           distance_m, hazard_exposure, operational_penalty, route_score, eta_minutes,
           instruction_text, warnings, hazard_alert_ids, trigger_reason)
        VALUES (:uid,:irid, ST_SetSRID(ST_MakePoint(:lng,:lat),4326), :shid, ST_SetSRID(ST_GeomFromText(:wkt),4326),
                :dist,:exp,:penalty,:score,:eta,:instr,:warn,CAST(:hids AS uuid[]),:reason)
        RETURNING id, computed_at
    """), {
        "uid": user_id, "irid": incident_report_id, "lng": lng, "lat": lat,
        "shid": best["safe_harbor_id"], "wkt": best["route_wkt"], "dist": best["distance_m"],
        "exp": best["hazard_exposure"], "penalty": best["operational_penalty"],
        "score": best["route_score"], "eta": best["eta_minutes"], "instr": instruction,
        "warn": json.dumps(warnings), "hids": best["hazard_alert_ids"], "reason": trigger_reason,
    }).mappings().first()
    db.commit()

    audit.log_audit_event(db, event_type="safe_harbor.guidance.computed", entity_type="safe_harbor_guidance",
                     entity_id=str(row["id"]), actor_type="system" if incident_report_id else "user",
                     actor_id=user_id, payload={"safe_harbor_id": best["safe_harbor_id"], "route_score": best["route_score"]})

    return {
        "guidance_id": str(row["id"]), "safe_harbor_id": str(best["safe_harbor_id"]), "safe_harbor_name": best["name"],
        "route_geojson": json.loads(best["route_geojson"]), "distance_m": best["distance_m"],
        "eta_minutes": best["eta_minutes"], "route_score": best["route_score"], "instruction": instruction,
        "warnings": warnings, "hazard_alert_ids": best["hazard_alert_ids"], "computed_at": row["computed_at"],
        "trigger_reason": trigger_reason,
    }
