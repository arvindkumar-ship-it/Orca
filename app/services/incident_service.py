# """
# Module 21 service layer — SOS/Incident API orchestration only.
# Actual routing/ranking logic lives in Module 8/9/10/11 services (assumed built):

# - app.services.dispatch_service.dispatch_incident(db, incident: IncidentReport)
#     -> DispatchResult(primary_targets: list[{type,name,status,target_id,jurisdiction_id}],
#                        ack_timeout_sec: int)
#   Creates IncidentRoute rows + starts escalation timer (Module 8 step 10-13, Module 9/10, Module 15).

# - app.services.safezone_service.get_nearest_safe_zone(db, lat, lng)
#     -> SafeZoneResult(name, distance_m, eta_min_walk) | None   (Module 11)

# - app.core.audit.log_audit_event(...)  (Module 18)
# """
# import uuid
# from datetime import datetime, timezone

# from sqlalchemy.orm import Session

# from app.core.exceptions import NotFoundError, ValidationError
# from app.core.audit import log_audit_event
# from app.models.incident import IncidentReport, IncidentRoute, IncidentStatusHistory, IncidentStatus
# from app.services.dispatch_service import dispatch_incident
# from app.services.safezone_service import get_nearest_safe_zone

# NEXT_ACTION = {
#     IncidentStatus.DISPATCHED: "await_acknowledgement",
#     IncidentStatus.ACKNOWLEDGED: "follow_safe_zone_route",
#     IncidentStatus.ROUTED: "follow_safe_zone_route",
#     IncidentStatus.EN_ROUTE: "stay_at_location",
#     IncidentStatus.HOSPITAL_NOTIFIED: "await_transfer",
#     IncidentStatus.SAFE_ZONE_SHARED: "follow_safe_zone_route",
#     IncidentStatus.RESOLVED: "incident_resolved",
#     IncidentStatus.CLOSED: "incident_closed",
# }


# def _set_status(db: Session, incident: IncidentReport, to_status: str, reason: str = None):
#     db.add(IncidentStatusHistory(incident_report_id=incident.id, from_status=incident.status,
#                                   to_status=to_status, reason=reason))
#     incident.status = to_status
#     incident.updated_at = datetime.now(timezone.utc)


# def create_sos(db: Session, payload) -> tuple[IncidentReport, object, object]:
#     loc = payload.location
#     incident = IncidentReport(
#         user_id=payload.user_id,
#         beach_id=payload.beach_id,
#         incident_type=payload.incident_type,
#         severity=payload.severity,
#         lat=loc.lat,
#         lng=loc.lng,
#         description=payload.notes,
#         media=[m.model_dump() for m in payload.media],
#         trigger_type=payload.trigger_type,
#         battery_pct=payload.device_state.battery_pct,
#         signal_strength=payload.device_state.signal_strength,
#         current_hazard_context=payload.hazard_context.model_dump(),
#         status=IncidentStatus.CREATED,
#     )
#     db.add(incident)
#     db.flush()  # incident.id available
#     _set_status(db, incident, IncidentStatus.LOCATION_LOCKED, reason="gps_locked")

#     result = dispatch_incident(db, incident)  # fan-out to 112/authority/hospital + escalation timer
#     _set_status(db, incident, IncidentStatus.DISPATCHED, reason="dispatch_fanout_complete")

#     safe_zone = get_nearest_safe_zone(db, loc.lat, loc.lng)

#     log_audit_event(db, event_type="sos.triggered", entity_type="incident_report", entity_id=incident.id,
#                      actor_type="user", actor_id=payload.user_id,
#                      payload={"trigger_type": payload.trigger_type, "severity": payload.severity})
#     db.commit()
#     db.refresh(incident)
#     return incident, result, safe_zone


# def _get(db: Session, incident_id: uuid.UUID) -> IncidentReport:
#     incident = db.query(IncidentReport).filter(IncidentReport.id == incident_id).first()
#     if not incident:
#         raise NotFoundError("Incident not found")
#     return incident


# def get_incident(db: Session, incident_id: uuid.UUID):
#     incident = _get(db, incident_id)
#     safe_zone = get_nearest_safe_zone(db, float(incident.lat), float(incident.lng))
#     routes = sorted(incident.routes, key=lambda r: r.route_rank)
#     authority = next((r for r in routes if r.target_type == "authority"), None)
#     hospital = next((r for r in routes if r.target_type == "hospital"), None)
#     primary = next((r for r in routes if r.target_type in ("112", "authority")), None)
#     return incident, safe_zone, authority, hospital, primary


# def get_incident_status(db: Session, incident_id: uuid.UUID):
#     incident = _get(db, incident_id)
#     acked = [r for r in incident.routes if r.ack_status in ("received", "accepted") and r.ack_time]
#     return incident, acked, NEXT_ACTION.get(incident.status, "await_dispatch")


# def attach_media(db: Session, incident_id: uuid.UUID, payload) -> uuid.UUID:
#     incident = _get(db, incident_id)
#     media_id = uuid.uuid4()
#     item = {"id": str(media_id), "type": payload.type, "url": payload.url, "caption": payload.caption}
#     incident.media = [*(incident.media or []), item]
#     incident.updated_at = datetime.now(timezone.utc)
#     db.commit()
#     return media_id


# def record_ack(db: Session, incident_id: uuid.UUID, payload) -> IncidentReport:
#     incident = _get(db, incident_id)
#     route = (
#         db.query(IncidentRoute)
#         .filter(IncidentRoute.incident_report_id == incident_id, IncidentRoute.target_type == payload.target_type,
#                 IncidentRoute.target_name == payload.target_name)
#         .first()
#     )
#     if not route:
#         raise ValidationError("No matching dispatch route for this target")

#     route.ack_status = payload.ack_status
#     route.ack_time = datetime.now(timezone.utc)
#     route.external_ref = payload.external_ref

#     if payload.ack_status in ("received", "accepted") and incident.status == IncidentStatus.DISPATCHED:
#         _set_status(db, incident, IncidentStatus.ACKNOWLEDGED, reason=f"{payload.target_name}_ack")

#     log_audit_event(db, event_type="authority.ack.received", entity_type="incident_report", entity_id=incident.id,
#                      actor_type="authority", actor_id=None,
#                      payload={"target_type": payload.target_type, "ack_status": payload.ack_status})
#     db.commit()
#     db.refresh(incident)
#     return incident





"""
Module 21 service layer — SOS/Incident API orchestration.

REWRITTEN — the original assumed a single `dispatch_service.dispatch_incident()` function.
The real architecture (confirmed from authority_router_service.py, hospital_router_service.py,
dispatch_state_machine.py) is: authority and hospital dispatch are two SEPARATE parallel calls
(route_to_authority, route_to_hospital — this matches hospital_router_service.py's own comment:
"hospital pre-alerted in parallel with authority dispatch, which is exactly what Module 8 does"),
and ALL incident_reports.status changes must go through DispatchStateMachine.transition() —
not a local _set_status() helper — because the state machine is what schedules ack-timers,
fires notifications, and validates the transition graph. The old _set_status() duplicated (and
bypassed) all of that.

get_nearest_safe_zone() never existed — replaced with the real safezone_service functions:
compute_safezone_guidance() (initial computation) and get_active_guidance() (re-fetch existing).

⚠️ ASSUMPTION — the `result` returned by create_sos() is now a dict describing both dispatch
calls' outcomes (routed_count, no_match flags, route ids) rather than the originally-assumed
DispatchResult(primary_targets, ack_timeout_sec) shape. Check the router/schema that consumes
this return value (incidents.py / schemas/incident.py) and adjust the response model if it
expects the old shape.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.exceptions import NotFoundError, ValidationError
from app.core.audit import log_audit_event
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.models.incident import IncidentReport, IncidentRoute, IncidentStatusHistory, IncidentStatus
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.authority_router_service import route_to_authority
from app.services.hospital_router_service import route_to_hospital
from app.core.dispatch_states import ACK_TIMEOUT_SECONDS
from app.services.safezone_service import compute_safezone_guidance, get_active_guidance
from app.services.sos_service import _dispatch_112
from app.services.tracking_service import start_tracking
from app.services.fanout_service import start_fanout

NEXT_ACTION = {
    IncidentStatus.DISPATCHED: "await_acknowledgement",
    IncidentStatus.ACKNOWLEDGED: "follow_safe_zone_route",
    IncidentStatus.ROUTED: "follow_safe_zone_route",
    IncidentStatus.EN_ROUTE: "stay_at_location",
    IncidentStatus.HOSPITAL_NOTIFIED: "await_transfer",
    IncidentStatus.SAFE_ZONE_SHARED: "follow_safe_zone_route",
    IncidentStatus.RESOLVED: "incident_resolved",
    IncidentStatus.CLOSED: "incident_closed",
}


def create_sos(db: Session, payload) -> tuple[IncidentReport, dict, dict | None]:
    loc = payload.location
    hazard_ctx = payload.hazard_context.model_dump()
    if payload.beach_id and payload.activity_type:
        risk_row = db.execute(text("""SELECT brs.risk_score, bf.wave_height
              FROM beach_risk_scores brs
              LEFT JOIN beach_forecasts bf ON bf.beach_id = brs.beach_id AND bf.forecast_time = brs.forecast_time
              WHERE brs.beach_id = :bid AND brs.activity_type = :at
              ORDER BY brs.computed_at DESC LIMIT 1"""),
              {"bid": str(payload.beach_id), "at": payload.activity_type}).mappings().first()
        if risk_row and risk_row["wave_height"] is not None:
            hazard_ctx["wave_height_m"] = float(risk_row["wave_height"])
    incident = IncidentReport(
        user_id=payload.user_id,
        beach_id=payload.beach_id,
        activity_type=payload.activity_type,
        incident_type=payload.incident_type,
        severity=payload.severity,
        lat=loc.lat,
        lng=loc.lng,
        description=payload.notes,
        media=[m.model_dump() for m in payload.media],
        trigger_type=payload.trigger_type,
        battery_pct=payload.device_state.battery_pct,
        signal_strength=payload.device_state.signal_strength,
        current_hazard_context=hazard_ctx,
        status=IncidentStatus.CREATED,
    )
    db.add(incident)
    db.flush()  # incident.id available

    sm = DispatchStateMachine(db)
    sm.transition(incident.id, IncidentState.VALIDATED, actor_type="system",
                  actor_id=None, reason="incident_validated")

    sm.transition(incident.id, IncidentState.LOCATION_LOCKED, actor_type="user",
                  actor_id=payload.user_id, reason="gps_locked")

    # Parallel fan-out — authority and hospital are dispatched independently, matching
    # Module 8's original "never rely on one responder only" rule.
    authority_result = route_to_authority(db, incident.id)
    hospital_result = route_to_hospital(db, incident.id)

    sm.transition(incident.id, IncidentState.PACKED, actor_type="system",
                  actor_id=None, reason="dispatch_packed")

    sm.transition(incident.id, IncidentState.DISPATCHED, actor_type="system", actor_id=None,
                  reason="dispatch_fanout_complete",
                  extra_payload={"authority_routed": authority_result["routed_count"],
                                 "hospital_matched": not hospital_result["no_match"]})

    # Bug G fix — these three were only wired into sos_service.create_sos_incident()
    # (offline-sync path), never into this function (live /v1/sos path). Each is its
    # own try/except so one failure never blocks the others or the SOS itself
    # (Module 33: no silent failure, but also no single point of failure).
    erss_result = {"attempted": True}
    try:
        erss_result = {"attempted": True, **_dispatch_112(db, incident.id)}
    except Exception as e:
        db.rollback()
        print(f"[BUG G] _dispatch_112 failed: {e}")
        erss_result = {"attempted": True, "error": str(e)}

    tracking_result = {"started": False}
    try:
        session_id = start_tracking(db, str(incident.id), payload.user_id)
        tracking_result = {"started": True, "session_id": session_id}
    except Exception as e:
        db.rollback()
        print(f"[BUG G] start_tracking failed: {e}")
        tracking_result = {"started": False, "error": str(e)}

    fanout_result = {"started": False}
    try:
        fanout_raw = start_fanout(db, str(incident.id), payload.user_id, None, True, True)
        fanout_result = {"started": True, "session_id": fanout_raw["session_id"]}
    except Exception as e:
        db.rollback()
        print(f"[BUG G] start_fanout failed: {e}")
        fanout_result = {"started": False, "error": str(e)}

    safe_zone = None
    try:
        safe_zone = compute_safezone_guidance(
            db, str(payload.user_id) if payload.user_id else None, loc.lat, loc.lng,
            beach_id=str(payload.beach_id) if payload.beach_id else None,
            incident_report_id=str(incident.id), trigger_reason="sos_created",
        )
    except ValueError:
        pass  # NO_SAFE_ZONE_FOUND_IN_RADIUS — incident still valid without one

    log_audit_event(db, event_type="sos.triggered", entity_type="incident_report", entity_id=incident.id,
                     actor_type="user", actor_id=payload.user_id,
                     payload={"trigger_type": payload.trigger_type, "severity": payload.severity})
    db.commit()
    db.refresh(incident)

    # Bug #8/#9/#11 fix — API layer (incidents.py) needs SOSResponse-shaped data
    # (ack_timeout_sec, primary_targets), not the raw authority/hospital dispatch dicts.
    # ack_timeout_sec comes from the state machine's own ack-timer constant (dispatch_states.py) —
    # this is the actual timeout the DispatchStateMachine just scheduled on entering DISPATCHED.
    # primary_targets is built from the real incident_routes rows just written by
    # route_to_authority/route_to_hospital, using the model's actual columns
    # (target_type, target_name, ack_status) — not invented fields.
    route_rows = db.query(IncidentRoute).filter(
        IncidentRoute.incident_report_id == incident.id,
        IncidentRoute.ack_status != "not_sent",
    ).order_by(IncidentRoute.route_rank).all()
    primary_targets = [
        {"type": r.target_type, "name": r.target_name, "status": r.ack_status} for r in route_rows
    ]

    result = {
        "authority": authority_result,
        "hospital": hospital_result,
        "ack_timeout_sec": ACK_TIMEOUT_SECONDS,
        "primary_targets": primary_targets,
    }
    return incident, result, safe_zone


def _get(db: Session, incident_id: uuid.UUID) -> IncidentReport:
    incident = db.query(IncidentReport).filter(IncidentReport.id == incident_id).first()
    if not incident:
        raise NotFoundError("Incident not found")
    return incident


def get_incident(db: Session, incident_id: uuid.UUID):
    incident = _get(db, incident_id)
    safe_zone = get_active_guidance(db, str(incident.user_id) if incident.user_id else None,
                                     incident_report_id=str(incident.id))
    routes = sorted(incident.routes, key=lambda r: r.route_rank)
    authority = next((r for r in routes if r.target_type == "authority"), None)
    hospital = next((r for r in routes if r.target_type == "hospital"), None)
    primary = next((r for r in routes if r.target_type in ("112", "authority")), None)
    return incident, safe_zone, authority, hospital, primary


def get_incident_status(db: Session, incident_id: uuid.UUID):
    incident = _get(db, incident_id)
    acked = [r for r in incident.routes if r.ack_status in ("received", "accepted", "acknowledged") and r.ack_time]
    return incident, acked, NEXT_ACTION.get(incident.status, "await_dispatch")


def attach_media(db: Session, incident_id: uuid.UUID, payload) -> uuid.UUID:
    incident = _get(db, incident_id)
    media_id = uuid.uuid4()
    item = {"id": str(media_id), "type": payload.type, "url": payload.url, "caption": payload.caption}
    incident.media = [*(incident.media or []), item]
    incident.updated_at = datetime.now(timezone.utc)
    db.commit()
    return media_id


def record_ack(db: Session, incident_id: uuid.UUID, payload) -> IncidentReport:
    """Generic ack recorder for route targets that don't have a dedicated ack endpoint
    (e.g. '112', 'contact'). Authority and hospital routes should go through
    authority_router_service.acknowledge_authority_route() / hospital_router_service.
    acknowledge_hospital_route() instead, since those correctly drive the state machine
    with the right target-specific IncidentState transition."""
    incident = _get(db, incident_id)
    route = (
        db.query(IncidentRoute)
        .filter(IncidentRoute.incident_report_id == incident_id, IncidentRoute.target_type == payload.target_type,
                IncidentRoute.target_name == payload.target_name)
        .first()
    )
    if not route:
        raise ValidationError("No matching dispatch route for this target")

    route.ack_status = payload.ack_status
    route.ack_time = datetime.now(timezone.utc)
    route.external_ref = payload.external_ref

    if payload.ack_status in ("received", "accepted") and incident.status == IncidentStatus.DISPATCHED:
        sm = DispatchStateMachine(db)
        try:
            sm.transition(incident.id, IncidentState.ACKNOWLEDGED, actor_type=payload.target_type,
                          reason=f"{payload.target_name}_ack")
        except InvalidTransitionError:
            pass  # route-level ack still recorded above even if state already moved on

    log_audit_event(db, event_type="authority.ack.received", entity_type="incident_report", entity_id=incident.id,
                     actor_type="authority", actor_id=None,
                     payload={"target_type": payload.target_type, "ack_status": payload.ack_status})
    db.commit()
    db.refresh(incident)
    return incident