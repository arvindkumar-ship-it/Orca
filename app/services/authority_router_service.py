# """
# Module 9 — Authority Router.
# Dispatch logic (route_to_authority) only writes incident_routes — never touches
# incident_reports.status, so it's unaffected by the state-machine migration.
# Only acknowledge_authority_route changes: it now drives DISPATCHED -> ACKNOWLEDGED
# through DispatchStateMachine instead of a raw UPDATE.
# """
# import json
# from sqlalchemy import text
# from sqlalchemy.orm import Session

# from app.core.config import settings
# from app.core.audit import log_audit_event
# from app.core.dispatch_states import IncidentState, InvalidTransitionError
# from app.services.dispatch_state_machine import DispatchStateMachine
# from app.services.channels.sms_channel import send_sms

# SEARCH_RADIUS_M = 20_000
# RESPONDER_AVG_SPEED_MPS = 11  # heuristic, distinct from hospital-router's ambulance constant
# WEIGHTS = {"alpha": 0.3, "beta": 0.2, "gamma": 0.2, "delta": 0.2, "eta": 0.1}


# def _required_classes(incident_type: str, severity: str) -> list[str]:
#     mapping = {
#         "drowning": ["lifeguard", "marine_police", "coast_guard"],
#         "missing_person": ["marine_police", "police"],
#         "harassment": ["police"],
#         "injury": ["police", "marine_police"],
#         "cyclone_storm_surge": ["district_disaster_authority", "marine_police", "coast_guard"],
#     }
#     if incident_type in mapping:
#         return mapping[incident_type]
#     return ["police", "marine_police", "district_disaster_authority"] if severity == "severe" else ["police"]


# def _find_jurisdiction_candidates(db: Session, lat: float, lng: float, classes: list[str]) -> list[dict]:
#     non_lifeguard = [c for c in classes if c != "lifeguard"]
#     if not non_lifeguard:
#         return []
#     rows = db.execute(text("""
#         SELECT id, name, authority_type, contact_phone, contact_email, escalation_level,
#                ST_Distance(service_area_geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m,
#                ST_Contains(service_area_geom, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)) AS inside
#         FROM jurisdictions
#         WHERE active = true AND authority_type = ANY(:classes)
#           AND ST_DWithin(service_area_geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
#         ORDER BY inside DESC, distance_m ASC LIMIT 10
#     """), {"lng": lng, "lat": lat, "classes": non_lifeguard, "radius": SEARCH_RADIUS_M}).mappings().all()
#     return [{"source_table": "jurisdictions", "target_id": r["id"], "name": r["name"], "authority_type": r["authority_type"],
#              "contact_phone": r["contact_phone"], "distance_m": float(r["distance_m"]), "inside": r["inside"]} for r in rows]


# def _find_lifeguard_candidates(db: Session, lat: float, lng: float, classes: list[str]) -> list[dict]:
#     if "lifeguard" not in classes:
#         return []
#     rows = db.execute(text("""
#         SELECT id, name, contact_phone,
#                ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m
#         FROM rescue_posts
#         WHERE active = true AND post_type = 'lifeguard'
#           AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
#         ORDER BY distance_m ASC LIMIT 5
#     """), {"lng": lng, "lat": lat, "radius": SEARCH_RADIUS_M}).mappings().all()
#     return [{"source_table": "rescue_posts", "target_id": r["id"], "name": r["name"], "authority_type": "lifeguard",
#              "contact_phone": r["contact_phone"], "distance_m": float(r["distance_m"]), "inside": True} for r in rows]


# def _score_authority(c: dict, required_classes: list[str]) -> dict:
#     eta_minutes = round((c["distance_m"] / RESPONDER_AVG_SPEED_MPS) / 60, 1)
#     proximity_score = 1 - min(c["distance_m"] / SEARCH_RADIUS_M, 1)
#     response_time_score = 1 / max(eta_minutes, 1)
#     jurisdiction_match_score = 1 if c["inside"] else 0.4
#     capability_score = 0.8 if c["authority_type"] in required_classes else 0.4
#     availability_score = 0.7  # heuristic — no live availability data source in schema

#     score = (WEIGHTS["alpha"] * proximity_score + WEIGHTS["beta"] * capability_score +
#              WEIGHTS["gamma"] * availability_score + WEIGHTS["delta"] * response_time_score +
#              WEIGHTS["eta"] * jurisdiction_match_score)
#     return {**c, "eta_minutes": eta_minutes, "score": round(score, 5)}


# def _build_packet(incident_report_id, lat: float, lng: float, incident_type: str, severity: str,
#                    eta_minutes: float, contact: str | None, notes: str) -> dict:
#     return {
#         "incident_report_id": str(incident_report_id), "location": {"lat": lat, "lng": lng},
#         "incident_type": incident_type, "severity": severity, "eta_minutes": eta_minutes,
#         "live_gps_link": f"{settings.APP_BASE_URL}/track/{incident_report_id}",
#         "reporting_contact": contact, "dispatcher_notes": notes,
#     }


# def _packet_to_sms(p: dict, name: str) -> str:
#     return (f"INCIDENT ALERT ({name}): {p['incident_type']} ({p['severity']}). ETA {p['eta_minutes']} min. "
#             f"Live: {p['live_gps_link']}. Reporter contact: {p['reporting_contact'] or 'N/A'}.")


# def _dispatch(db: Session, incident_report_id, route_rank: int, jurisdiction_id, a: dict, packet: dict) -> str:
#     row = db.execute(text("""
#         INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, jurisdiction_id, route_rank, ack_status, packet_payload)
#         VALUES (:irid,'authority',:name,:tid,:jid,:rank,'sent',:packet) RETURNING id
#     """), {"irid": incident_report_id, "name": a["name"], "tid": a["target_id"], "jid": jurisdiction_id,
#            "rank": route_rank, "packet": json.dumps(packet)}).mappings().first()
#     route_id = str(row["id"])

#     sms_result = send_sms(a.get("contact_phone") or "", _packet_to_sms(packet, a["name"]))
#     if not sms_result["ok"]:
#         db.execute(text("UPDATE incident_routes SET last_error = :e WHERE id = :id"), {"e": sms_result.get("error"), "id": route_id})

#     log_audit_event(db, event_type="authority.dispatched", entity_type="incident_route", entity_id=route_id,
#                      actor_type="system", actor_id=None,
#                      payload={"target_id": str(a["target_id"]), "authority_type": a["authority_type"], "score": a["score"], "rank": route_rank})
#     return route_id


# def route_to_authority(db: Session, incident_report_id) -> dict:
#     ir = db.execute(text("""SELECT lat, lng, incident_type, severity, description, user_id
#                              FROM incident_reports WHERE id = :id"""), {"id": incident_report_id}).mappings().first()
#     if not ir:
#         raise ValueError("INCIDENT_NOT_FOUND")

#     required_classes = _required_classes(ir["incident_type"], ir["severity"])
#     jur = _find_jurisdiction_candidates(db, float(ir["lat"]), float(ir["lng"]), required_classes)
#     lg = _find_lifeguard_candidates(db, float(ir["lat"]), float(ir["lng"]), required_classes)
#     candidates = jur + lg

#     if not candidates:
#         log_audit_event(db, event_type="authority.no_match", entity_type="incident_report",
#                          entity_id=incident_report_id, actor_type="system", actor_id=None,
#                          payload={"required_classes": required_classes})
#         return {"routed_count": 0, "route_ids": [], "no_match": True}

#     ranked = sorted((_score_authority(c, required_classes) for c in candidates), key=lambda x: -x["score"])

#     reporting_contact = None
#     if ir["user_id"]:
#         u = db.execute(text("SELECT phone FROM users WHERE id = :id"), {"id": ir["user_id"]}).mappings().first()
#         reporting_contact = u["phone"] if u else None

#     top_k, rest = ranked[:2], ranked[2:]
#     route_ids = []
#     for i, a in enumerate(top_k):
#         packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
#                                 ir["severity"], a["eta_minutes"], reporting_contact, ir["description"] or "")
#         jurisdiction_id = a["target_id"] if a["source_table"] == "jurisdictions" else None
#         route_ids.append(_dispatch(db, incident_report_id, i + 1, jurisdiction_id, a, packet))

#     for i, a in enumerate(rest):
#         packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
#                                 ir["severity"], a["eta_minutes"], reporting_contact, ir["description"] or "")
#         jurisdiction_id = a["target_id"] if a["source_table"] == "jurisdictions" else None
#         db.execute(text("""
#             INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, jurisdiction_id, route_rank, ack_status, packet_payload)
#             VALUES (:irid,'authority',:name,:tid,:jid,:rank,'not_sent',:packet)
#         """), {"irid": incident_report_id, "name": a["name"], "tid": a["target_id"], "jid": jurisdiction_id,
#                "rank": len(top_k) + i + 1, "packet": json.dumps(packet)})

#     db.commit()
#     return {"routed_count": len(route_ids), "route_ids": route_ids, "no_match": False}


# def acknowledge_authority_route(db: Session, route_id: str) -> None:
#     """CHANGED: was a raw UPDATE incident_reports.status='routed'. Now goes through
#     DispatchStateMachine: DISPATCHED -> ACKNOWLEDGED (valid per TRANSITIONS graph).
#     This also auto-cancels the pending ack_timer via DispatchStateMachine._on_enter."""
#     row = db.execute(text("""UPDATE incident_routes SET ack_status = 'acknowledged', ack_time = now()
#                               WHERE id = :id AND target_type = 'authority' RETURNING incident_report_id"""),
#                       {"id": route_id}).mappings().first()
#     if not row:
#         raise ValueError("ROUTE_NOT_FOUND")

#     sm = DispatchStateMachine(db)
#     try:
#         sm.transition(row["incident_report_id"], IncidentState.ACKNOWLEDGED,
#                        actor_type="authority", reason="authority_ack_received")
#         db.commit()
#     except InvalidTransitionError:
#         # Incident already moved past DISPATCHED (e.g. hospital ack raced ahead, or ops force-closed).
#         # Route-level ack is still recorded above — don't lose that — just skip the state transition.
#         db.commit()

"""
Module 9 — Authority Router.
Dispatch logic (route_to_authority) only writes incident_routes — never touches
incident_reports.status, so it's unaffected by the state-machine migration.
Only acknowledge_authority_route changes: it now drives DISPATCHED -> ACKNOWLEDGED
through DispatchStateMachine instead of a raw UPDATE.
"""
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.audit import log_audit_event
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.channels.sms_channel import send_sms

SEARCH_RADIUS_M = 20_000
RESPONDER_AVG_SPEED_MPS = 11  # heuristic, distinct from hospital-router's ambulance constant
WEIGHTS = {"alpha": 0.3, "beta": 0.2, "gamma": 0.2, "delta": 0.2, "eta": 0.1}


def _required_classes(incident_type: str, severity: str) -> list[str]:
    mapping = {
        "drowning": ["lifeguard", "marine_police", "coast_guard"],
        "missing_person": ["marine_police", "local_police"],
        "harassment": ["local_police"],
        "injury": ["local_police", "marine_police"],
        "cyclone_storm_surge": ["district_disaster_authority", "marine_police", "coast_guard"],
    }
    if incident_type in mapping:
        return mapping[incident_type]
    return ["local_police", "marine_police", "district_disaster_authority"] if severity == "severe" else ["local_police"]


def _find_jurisdiction_candidates(db: Session, lat: float, lng: float, classes: list[str]) -> list[dict]:
    non_lifeguard = [c for c in classes if c != "lifeguard"]
    if not non_lifeguard:
        return []
    rows = db.execute(text("""
        SELECT id, name, authority_type, contact_phone, contact_email, escalation_level,
               ST_Distance(service_area_geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m,
               ST_Contains(service_area_geom, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)) AS inside
        FROM jurisdictions
        WHERE active = true AND authority_type = ANY(:classes)
          AND ST_DWithin(service_area_geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY inside DESC, distance_m ASC LIMIT 10
    """), {"lng": lng, "lat": lat, "classes": non_lifeguard, "radius": SEARCH_RADIUS_M}).mappings().all()
    return [{"source_table": "jurisdictions", "target_id": r["id"], "name": r["name"], "authority_type": r["authority_type"],
             "contact_phone": r["contact_phone"], "distance_m": float(r["distance_m"]), "inside": r["inside"]} for r in rows]


def _find_lifeguard_candidates(db: Session, lat: float, lng: float, classes: list[str]) -> list[dict]:
    if "lifeguard" not in classes:
        return []
    rows = db.execute(text("""
        SELECT id, name, contact_phone,
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) AS distance_m
        FROM rescue_posts
        WHERE active = true AND post_type = 'lifeguard'
          AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)
        ORDER BY distance_m ASC LIMIT 5
    """), {"lng": lng, "lat": lat, "radius": SEARCH_RADIUS_M}).mappings().all()
    return [{"source_table": "rescue_posts", "target_id": r["id"], "name": r["name"], "authority_type": "lifeguard",
             "contact_phone": r["contact_phone"], "distance_m": float(r["distance_m"]), "inside": True} for r in rows]


def _score_authority(c: dict, required_classes: list[str]) -> dict:
    eta_minutes = round((c["distance_m"] / RESPONDER_AVG_SPEED_MPS) / 60, 1)
    proximity_score = 1 - min(c["distance_m"] / SEARCH_RADIUS_M, 1)
    response_time_score = 1 / max(eta_minutes, 1)
    jurisdiction_match_score = 1 if c["inside"] else 0.4
    capability_score = 0.8 if c["authority_type"] in required_classes else 0.4
    availability_score = 0.7  # heuristic — no live availability data source in schema

    score = (WEIGHTS["alpha"] * proximity_score + WEIGHTS["beta"] * capability_score +
             WEIGHTS["gamma"] * availability_score + WEIGHTS["delta"] * response_time_score +
             WEIGHTS["eta"] * jurisdiction_match_score)
    return {**c, "eta_minutes": eta_minutes, "score": round(score, 5)}


def _build_packet(incident_report_id, lat: float, lng: float, incident_type: str, severity: str,
                   eta_minutes: float, contact: str | None, notes: str) -> dict:
    return {
        "incident_report_id": str(incident_report_id), "location": {"lat": lat, "lng": lng},
        "incident_type": incident_type, "severity": severity, "eta_minutes": eta_minutes,
        "live_gps_link": f"{settings.APP_BASE_URL}/track/{incident_report_id}",
        "reporting_contact": contact, "dispatcher_notes": notes,
    }


def _packet_to_sms(p: dict, name: str) -> str:
    return (f"INCIDENT ALERT ({name}): {p['incident_type']} ({p['severity']}). ETA {p['eta_minutes']} min. "
            f"Live: {p['live_gps_link']}. Reporter contact: {p['reporting_contact'] or 'N/A'}.")


def _dispatch(db: Session, incident_report_id, route_rank: int, jurisdiction_id, a: dict, packet: dict) -> str:
    row = db.execute(text("""
        INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, jurisdiction_id, route_rank, ack_status, packet_payload)
        VALUES (:irid,'authority',:name,:tid,:jid,:rank,'sent',:packet) RETURNING id
    """), {"irid": incident_report_id, "name": a["name"], "tid": a["target_id"], "jid": jurisdiction_id,
           "rank": route_rank, "packet": json.dumps(packet)}).mappings().first()
    route_id = str(row["id"])

    sms_result = send_sms(a.get("contact_phone") or "", _packet_to_sms(packet, a["name"]))
    if not sms_result["ok"]:
        db.execute(text("UPDATE incident_routes SET last_error = :e WHERE id = :id"), {"e": sms_result.get("error"), "id": route_id})

    log_audit_event(db, event_type="authority.dispatched", entity_type="incident_route", entity_id=route_id,
                     actor_type="system", actor_id=None,
                     payload={"target_id": str(a["target_id"]), "authority_type": a["authority_type"], "score": a["score"], "rank": route_rank})
    return route_id


def route_to_authority(db: Session, incident_report_id) -> dict:
    ir = db.execute(text("""SELECT lat, lng, incident_type, severity, description, user_id
                             FROM incident_reports WHERE id = :id"""), {"id": incident_report_id}).mappings().first()
    if not ir:
        raise ValueError("INCIDENT_NOT_FOUND")

    required_classes = _required_classes(ir["incident_type"], ir["severity"])
    jur = _find_jurisdiction_candidates(db, float(ir["lat"]), float(ir["lng"]), required_classes)
    lg = _find_lifeguard_candidates(db, float(ir["lat"]), float(ir["lng"]), required_classes)
    candidates = jur + lg

    if not candidates:
        log_audit_event(db, event_type="authority.no_match", entity_type="incident_report",
                         entity_id=incident_report_id, actor_type="system", actor_id=None,
                         payload={"required_classes": required_classes})
        return {"routed_count": 0, "route_ids": [], "no_match": True}

    ranked = sorted((_score_authority(c, required_classes) for c in candidates), key=lambda x: -x["score"])

    reporting_contact = None
    if ir["user_id"]:
        u = db.execute(text("SELECT phone FROM users WHERE id = :id"), {"id": ir["user_id"]}).mappings().first()
        reporting_contact = u["phone"] if u else None

    top_k, rest = ranked[:2], ranked[2:]
    route_ids = []
    for i, a in enumerate(top_k):
        packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
                                ir["severity"], a["eta_minutes"], reporting_contact, ir["description"] or "")
        jurisdiction_id = a["target_id"] if a["source_table"] == "jurisdictions" else None
        route_ids.append(_dispatch(db, incident_report_id, i + 1, jurisdiction_id, a, packet))

    for i, a in enumerate(rest):
        packet = _build_packet(incident_report_id, float(ir["lat"]), float(ir["lng"]), ir["incident_type"],
                                ir["severity"], a["eta_minutes"], reporting_contact, ir["description"] or "")
        jurisdiction_id = a["target_id"] if a["source_table"] == "jurisdictions" else None
        db.execute(text("""
            INSERT INTO incident_routes (incident_report_id, target_type, target_name, target_id, jurisdiction_id, route_rank, ack_status, packet_payload)
            VALUES (:irid,'authority',:name,:tid,:jid,:rank,'not_sent',:packet)
        """), {"irid": incident_report_id, "name": a["name"], "tid": a["target_id"], "jid": jurisdiction_id,
               "rank": len(top_k) + i + 1, "packet": json.dumps(packet)})

    db.commit()
    return {"routed_count": len(route_ids), "route_ids": route_ids, "no_match": False}


def acknowledge_authority_route(db: Session, route_id: str) -> None:
    """CHANGED: was a raw UPDATE incident_reports.status='routed'. Now goes through
    DispatchStateMachine: DISPATCHED -> ACKNOWLEDGED (valid per TRANSITIONS graph).
    This also auto-cancels the pending ack_timer via DispatchStateMachine._on_enter."""
    row = db.execute(text("""UPDATE incident_routes SET ack_status = 'acknowledged', ack_time = now()
                              WHERE id = :id AND target_type = 'authority' RETURNING incident_report_id"""),
                      {"id": route_id}).mappings().first()
    if not row:
        raise ValueError("ROUTE_NOT_FOUND")

    sm = DispatchStateMachine(db)
    try:
        sm.transition(row["incident_report_id"], IncidentState.ACKNOWLEDGED,
                       actor_type="authority", reason="authority_ack_received")
        db.commit()
    except InvalidTransitionError:
        # Incident already moved past DISPATCHED (e.g. hospital ack raced ahead, or ops force-closed).
        # Route-level ack is still recorded above — don't lose that — just skip the state transition.
        db.commit()