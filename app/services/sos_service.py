"""
Module 8 — SOS / Emergency Dispatch orchestrator.
Called from Module 21's POST /v1/sos (not exposed as its own route — Module 21 owns that path).

Status is now owned entirely by Module 27's DispatchStateMachine — this file never writes
incident_reports.status directly. Every lifecycle step is a validated transition.
"""
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import log_audit_event
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.authority_router_service import route_to_authority
from app.services.hospital_router_service import route_to_hospital
from app.services.tracking_service import start_tracking
from app.services.fanout_service import start_fanout


def _current_risk_context(db: Session, beach_id: str | None, activity_type: str | None) -> dict:
    if not beach_id or not activity_type:
        return {}
    try:
        row = db.execute(text("""SELECT brs.risk_score, brs.verdict, bf.wave_height
              FROM beach_risk_scores brs
              LEFT JOIN beach_forecasts bf ON bf.beach_id = brs.beach_id AND bf.forecast_time = brs.forecast_time
              WHERE brs.beach_id = :bid AND brs.activity_type = :at
              ORDER BY brs.computed_at DESC LIMIT 1"""),
              {"bid": beach_id, "at": activity_type}).mappings().first()
        if not row:
            return {}
        ctx = {"current_risk_score": float(row["risk_score"]), "verdict": row["verdict"]}
        if row["wave_height"] is not None:
            ctx["wave_height_m"] = float(row["wave_height"])
        return ctx
    except Exception:
        return {}  # never block SOS creation on risk-engine lookup failure


def _create_incident_record(db: Session, user_id: str, body) -> dict:
    """Creates the row in status='created' (matches IncidentState.CREATED default),
    then drives it forward through the state machine, not raw UPDATEs."""
    hazard_context = _current_risk_context(db, body.beach_id, body.activity_type)

    row = db.execute(text("""
        INSERT INTO incident_reports
          (user_id, beach_id, incident_type, severity, lat, lng, description, media, status,
           trigger_type, battery_pct, signal_strength, current_hazard_context, client_incident_id)
        VALUES (:uid,:bid,:itype,:sev,:lat,:lng,:desc,:media,:initial_status,:trig,:batt,:sig,:hazard,:cid)
        RETURNING id, created_at
    """), {"uid": user_id, "bid": body.beach_id, "itype": body.incident_type, "sev": body.severity,
           "lat": body.lat, "lng": body.lng, "desc": body.description, "media": json.dumps(body.media_urls),
           "initial_status": IncidentState.CREATED.value, "trig": body.trigger_type,
           "batt": body.battery_pct, "sig": body.signal_strength, "hazard": json.dumps(hazard_context),
           "cid": getattr(body, "client_incident_id", None)}).mappings().first()
    incident_id = row["id"]
    db.flush()

    sm = DispatchStateMachine(db)
    sm.transition(incident_id, IncidentState.VALIDATED, actor_type="system", reason="SOS payload validated")
    sm.transition(incident_id, IncidentState.LOCATION_LOCKED, actor_type="system",
                   reason=f"Location locked via {body.location_source}, accuracy {body.accuracy_m or 'unknown'}m")
    sm.transition(incident_id, IncidentState.PACKED, actor_type="system", reason="Incident packet built")
    db.commit()

    log_audit_event(db, event_type="sos.triggered", entity_type="incident_report", entity_id=incident_id,
                     actor_type="user", actor_id=user_id,
                     payload={"trigger_type": body.trigger_type, "incident_type": body.incident_type, "severity": body.severity})
    return {"incident_id": str(incident_id), "created_at": row["created_at"]}


def _dispatch_112(db: Session, incident_id) -> dict:
    """112 fan-out channel is a routing target, NOT the same as IncidentState.FALLBACK_112
    (that's the escalation-branch state for when primary/backup targets don't ack)."""
    try:
        row = db.execute(text("""INSERT INTO incident_routes (incident_report_id, target_type, target_name, route_rank, ack_status)
                                  VALUES (:id,'112','ERSS-112',0,'sent') RETURNING id"""), {"id": incident_id}).mappings().first()
        log_audit_event(db, event_type="incident.dispatched", entity_type="incident_route", entity_id=row["id"],
                         actor_type="system", actor_id=None, payload={"target": "112"})
        return {"route_id": str(row["id"])}
    except Exception as e:
        return {"error": str(e)}


def create_sos_incident(db: Session, user_id: str, body) -> dict:
    incident = _create_incident_record(db, user_id, body)
    incident_id = incident["incident_id"]

    sm = DispatchStateMachine(db)
    try:
        sm.transition(incident_id, IncidentState.DISPATCHED, actor_type="system",
                       reason="Fan-out to all responder channels initiated")
        db.commit()
    except InvalidTransitionError as e:
        db.rollback()
        raise  # incident creation itself succeeded but is now in a bad state — surface loudly, don't swallow

    # Each channel captured independently — one channel's failure never hides another's outcome
    # or blocks the others (Module 33: no silent failure).
    route_status = {}

    try:
        auth_result = route_to_authority(db, incident_id)
        route_status["authority"] = {"attempted": True, "routed_count": auth_result["routed_count"]}
    except Exception as e:
        db.rollback()
        route_status["authority"] = {"attempted": True, "error": str(e)}

    try:
        hosp_result = route_to_hospital(db, incident_id)
        route_status["hospital"] = {"attempted": True, "route_id": hosp_result.get("primary_route_id")}
    except Exception as e:
        db.rollback()
        route_status["hospital"] = {"attempted": True, "error": str(e)}

    erss_result = _dispatch_112(db, incident_id)
    route_status["erss112"] = {"attempted": True, **erss_result}

    try:
        session_id = start_tracking(db, str(incident_id), user_id)
        route_status["live_tracking"] = {"started": True, "session_id": session_id}
    except Exception as e:
        db.rollback()
        route_status["live_tracking"] = {"started": False, "error": str(e)}

    try:
        fanout_result = start_fanout(db, str(incident_id), user_id, None, True, True)
        route_status["contact_fanout"] = {"started": True, "session_id": fanout_result["session_id"]}
    except Exception as e:
        db.rollback()
        route_status["contact_fanout"] = {"started": False, "error": str(e)}

    failures = {k: v for k, v in route_status.items() if v.get("error") or v.get("started") is False}
    if failures:
        log_audit_event(db, event_type="sos.partial_dispatch_failure", entity_type="incident_report",
                         entity_id=incident_id, actor_type="system", actor_id=None, payload={"failures": failures})

    contacts = db.execute(text("SELECT name, phone FROM emergency_contacts WHERE user_id = :uid ORDER BY priority ASC"),
                           {"uid": user_id}).mappings().all()
    current_state = sm.get_current_state(incident_id)  # authoritative status, post-fanout

    return {
        "incident_id": str(incident_id), "created_at": incident["created_at"].isoformat(),
        "status": current_state.value, "route_status": route_status,
        "emergency_contacts": [dict(c) for c in contacts],
    }


def get_incident_status(db: Session, incident_id: str, user_id: str) -> dict:
    row = db.execute(text("""
        SELECT ir.id, ir.status, ir.incident_type, ir.severity, ir.created_at,
               json_agg(json_build_object(
                 'target_type', rt.target_type, 'target_name', rt.target_name,
                 'ack_status', rt.ack_status, 'ack_time', rt.ack_time, 'route_rank', rt.route_rank
               ) ORDER BY rt.route_rank) FILTER (WHERE rt.id IS NOT NULL) AS routes
        FROM incident_reports ir LEFT JOIN incident_routes rt ON rt.incident_report_id = ir.id
        WHERE ir.id = :id AND ir.user_id = :uid GROUP BY ir.id
    """), {"id": incident_id, "uid": user_id}).mappings().first()
    if not row:
        raise ValueError("INCIDENT_NOT_FOUND")
    return dict(row)
