"""
Module 10 — Hospital Router. Same treatment as Module 9: dispatch logic unchanged,
only acknowledge_hospital_route now drives the state machine.
"""
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.audit import log_audit_event
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.channels.sms_channel import send_sms

SEARCH_RADIUS_M = 15_000
AMBULANCE_AVG_SPEED_MPS = 8.3  # heuristic, shared with tracking_service
WEIGHTS = {"mu1": 0.35, "mu2": 0.25, "mu3": 0.2, "mu4": 0.15, "mu5": 0.05}
CAPACITY_SCORE = {"available": 1, "limited": 0.5, "full": 0.1, "unknown": 0.3}


def _required_capabilities(incident_type: str, severity: str) -> dict:
    base = {"trauma": False, "icu": False, "pediatric": False, "oxygen": False, "coastal_access": True}
    if incident_type == "drowning":
        return {**base, "trauma": True, "oxygen": True, "icu": severity == "severe"}
    if incident_type == "injury":
        return {**base, "trauma": True, "icu": severity == "severe"}
    if incident_type == "cyclone_storm_surge":
        return {**base, "trauma": True, "icu": True, "oxygen": True}
    return base


def _find_candidates(db: Session, lat: float, lng: float, req: dict) -> list[dict]:
    rows = db.execute(text("""
        SELECT id, name, contact_phone, contact_email, capabilities, capacity_status,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m
        FROM hospitals
        WHERE active = true
          AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
          AND (NOT :trauma OR (capabilities->>'trauma')::boolean IS TRUE)
          AND (NOT :icu OR (capabilities->>'icu')::boolean IS TRUE)
          AND (NOT :oxygen OR (capabilities->>'oxygen')::boolean IS TRUE)
        ORDER BY distance_m ASC LIMIT 10
    """), {"lng": lng, "lat": lat, "radius": SEARCH_RADIUS_M,
           "trauma": req["trauma"], "icu": req["icu"], "oxygen": req["oxygen"]}).mappings().all()
    return [dict(r) for r in rows]


def _specialty_match_score(capabilities: dict, req: dict) -> float:
    keys = list(req.keys())
    matched = sum(1 for k in keys if not req[k] or capabilities.get(k) is True)
    return matched / len(keys)


def _capability_coverage_score(capabilities: dict) -> float:
    flags = sum(1 for v in capabilities.values() if v is True)
    return min(flags / 4, 1)


def _score_hospital(c: dict, req: dict) -> dict:
    eta_minutes = round((float(c["distance_m"]) / AMBULANCE_AVG_SPEED_MPS) / 60, 1)
    eta_inv = 1 / max(eta_minutes, 1)
    capacity_score = CAPACITY_SCORE.get(c["capacity_status"], 0.3)
    specialty_score = _specialty_match_score(c["capabilities"], req)
    capability_score = _capability_coverage_score(c["capabilities"])
    confidence = 0.7  # heuristic — no capacity-freshness timestamp in schema

    score = (WEIGHTS["mu1"] * eta_inv + WEIGHTS["mu2"] * capability_score + WEIGHTS["mu3"] * capacity_score +
             WEIGHTS["mu4"] * specialty_score + WEIGHTS["mu5"] * confidence)
    return {**c, "eta_minutes": eta_minutes, "score": round(score, 5)}


def _build_packet(incident_report_id, lat: float, lng: float, incident_type: str, severity: str,
                   eta_minutes: float, patient_flags: list[str], accompanying_contact: str | None, notes: str) -> dict:
    return {
        "incident_report_id": str(incident_report_id), "location": {"lat": lat, "lng": lng},
        "incident_type": incident_type, "severity": severity, "eta_minutes": eta_minutes,
        "patient_condition_flags": patient_flags, "age_gender": None,
        "live_gps_link": f"{settings.APP_BASE_URL}/track/{incident_report_id}",
        "accompanying_contact": accompanying_contact, "dispatcher_notes": notes,
    }


def _packet_to_sms(p: dict) -> str:
    return (f"PRE-ARRIVAL ALERT: {p['incident_type']} ({p['severity']}). ETA {p['eta_minutes']} min. "
            f"Flags: {', '.join(p['patient_condition_flags']) or 'none'}. Live: {p['live_gps_link']}. "
            f"Contact: {p['accompanying_contact'] or 'N/A'}.")


def _dispatch(db: Session, incident_report_id, route_rank: int, hospital: dict, packet: dict) -> str:
    row = db.execute(text("""
        INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, route_rank, ack_status, packet_payload)
        VALUES (:irid,'hospital',:name,:hid,:rank,'sent',:packet) RETURNING id
    """), {"irid": incident_report_id, "name": hospital["name"], "hid": hospital["id"],
           "rank": route_rank, "packet": json.dumps(packet)}).mappings().first()
    route_id = str(row["id"])

    sms_result = send_sms(hospital.get("contact_phone") or "", _packet_to_sms(packet))
    if not sms_result["ok"]:
        db.execute(text("UPDATE incident_routes SET last_error = :e WHERE id = :id"),
                   {"e": sms_result.get("error"), "id": route_id})

    log_audit_event(db, event_type="hospital.dispatched", entity_type="incident_route", entity_id=route_id,
                     actor_type="system", actor_id=None,
                     payload={"hospital_id": str(hospital["id"]), "score": hospital["score"], "rank": route_rank})
    return route_id


def route_to_hospital(db: Session, incident_report_id) -> dict:
    ir = db.execute(text("""SELECT lat, lng, incident_type, severity, description, user_id
                             FROM incident_reports WHERE id = :id"""), {"id": incident_report_id}).mappings().first()
    if not ir:
        raise ValueError("INCIDENT_NOT_FOUND")

    req = _required_capabilities(ir["incident_type"], ir["severity"])
    candidates = _find_candidates(db, float(ir["lat"]), float(ir["lng"]), req)

    if not candidates:
        log_audit_event(db, event_type="hospital.no_match", entity_type="incident_report",
                         entity_id=incident_report_id, actor_type="system", actor_id=None,
                         payload={"required_capabilities": req})
        return {"primary_route_id": None, "backup_route_id": None, "no_match": True}

    ranked = sorted((_score_hospital(c, req) for c in candidates), key=lambda x: -x["score"])
    primary, backup = ranked[0], (ranked[1] if len(ranked) > 1 else None)
    patient_flags = [ir["incident_type"]] + (["high_severity"] if ir["severity"] == "severe" else [])

    accompanying_contact = None
    if ir["user_id"]:
        u = db.execute(text("SELECT phone FROM users WHERE id = :id"), {"id": ir["user_id"]}).mappings().first()
        accompanying_contact = u["phone"] if u else None

    primary_packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
                                    ir["severity"], primary["eta_minutes"], patient_flags, accompanying_contact, ir["description"] or "")
    primary_route_id = _dispatch(db, incident_report_id, 1, primary, primary_packet)

    backup_route_id = None
    if backup:
        backup_packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
                                       ir["severity"], backup["eta_minutes"], patient_flags, accompanying_contact, ir["description"] or "")
        row = db.execute(text("""
            INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, route_rank, ack_status, packet_payload)
            VALUES (:irid,'hospital',:name,:hid,2,'not_sent',:packet) RETURNING id
        """), {"irid": incident_report_id, "name": backup["name"], "hid": backup["id"], "packet": json.dumps(backup_packet)}).mappings().first()
        backup_route_id = str(row["id"])

    db.commit()
    return {"primary_route_id": primary_route_id, "backup_route_id": backup_route_id, "no_match": False}


def acknowledge_hospital_route(db: Session, route_id: str) -> None:
    """CHANGED: was a raw UPDATE incident_reports.status='hospital_notified'. Now goes through
    DispatchStateMachine. NOTE: per TRANSITIONS graph, HOSPITAL_NOTIFIED is only reachable
    FROM en_route, not directly from dispatched/acknowledged/routed. If hospital ack can
    legitimately arrive before EN_ROUTE (e.g. hospital pre-alerted in parallel with authority
    dispatch, which is exactly what Module 8 does), this WILL raise InvalidTransitionError
    until the incident has passed through ROUTED -> EN_ROUTE first. This is a real sequencing
    gap between Module 8's parallel dispatch and Module 27's linear graph — unresolved,
    flagged, not guessed at. Handling it defensively below: hospital ack is always recorded
    on the route regardless, and the state transition is attempted but not fatal if it's
    out of sequence."""
    row = db.execute(text("""UPDATE incident_routes SET ack_status = 'acknowledged', ack_time = now()
                              WHERE id = :id AND target_type = 'hospital' RETURNING incident_report_id"""),
                      {"id": route_id}).mappings().first()
    if not row:
        raise ValueError("ROUTE_NOT_FOUND")

    sm = DispatchStateMachine(db)
    try:
        sm.transition(row["incident_report_id"], IncidentState.HOSPITAL_NOTIFIED,
                       actor_type="hospital", reason="hospital_ack_received")
        db.commit()
    except InvalidTransitionError:
        db.commit()  # route-level ack preserved; state transition skipped — see note above
