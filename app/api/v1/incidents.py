# """Module 21 — API Layer: SOS / Incidents. Thin controllers only; logic in Module 8-11/18 services."""
# import uuid
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.orm import Session

# from app.core.db import get_db
# from app.core.exceptions import NotFoundError, ValidationError
# from app.schemas.incident import (
#     SOSRequest, SOSResponse, TargetStatus, SafeZoneInfo,
#     IncidentDetailResponse, RiskState, RoutingInfo, IncidentSafeZone, IncidentTimestamps,
#     IncidentStatusResponse, AckEntry,
#     MediaAttachRequest, MediaAttachResponse,
#     AckRequest, AckResponse,
# )
# from app.services import incident_service

# sos_router = APIRouter(prefix="/v1/sos", tags=["sos"])
# incidents_router = APIRouter(prefix="/v1/incidents", tags=["incidents"])


# def _handle(fn, *args, **kwargs):
#     try:
#         return fn(*args, **kwargs)
#     except NotFoundError as e:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
#     except ValidationError as e:
#         raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# @sos_router.post("", response_model=SOSResponse, status_code=status.HTTP_201_CREATED)
# def trigger_sos(payload: SOSRequest, db: Session = Depends(get_db)):
#     incident, result, safe_zone = _handle(incident_service.create_sos, db, payload)
#     return SOSResponse(
#         incident_id=incident.id,
#         status=incident.status,
#         location_locked=True,
#         ack_timeout_sec=result.ack_timeout_sec,
#         primary_targets=[TargetStatus(**t) for t in result.primary_targets],
#         safe_zone=SafeZoneInfo(**safe_zone.__dict__) if safe_zone else None,
#         message="Help has been alerted. Stay near your location and follow safe-zone guidance.",
#     )


# @incidents_router.get("/{incident_id}", response_model=IncidentDetailResponse)
# def get_incident(incident_id: uuid.UUID, db: Session = Depends(get_db)):
#     incident, safe_zone, authority, hospital, primary = _handle(incident_service.get_incident, db, incident_id)
#     return IncidentDetailResponse(
#         incident_id=incident.id,
#         status=incident.status,
#         incident_type=incident.incident_type,
#         severity=incident.severity,
#         current_location={"lat": float(incident.lat), "lng": float(incident.lng)},
#         risk_state=RiskState(
#             beach_verdict=incident.current_hazard_context.get("current_verdict"),
#             hazards=incident.current_hazard_context.get("alert_flags", []),
#             eta_minutes=incident.current_hazard_context.get("eta_minutes"),
#         ),
#         routing=RoutingInfo(
#             primary_authority=authority.target_name if authority else None,
#             hospital=hospital.target_name if hospital else None,
#             contact_status=primary.ack_status if primary else None,
#         ),
#         safe_zone=IncidentSafeZone(name=safe_zone.name, route_eta_min=safe_zone.eta_min_walk) if safe_zone else None,
#         timestamps=IncidentTimestamps(created_at=incident.created_at, last_update=incident.updated_at),
#     )


# @incidents_router.get("/{incident_id}/status", response_model=IncidentStatusResponse)
# def get_incident_status(incident_id: uuid.UUID, db: Session = Depends(get_db)):
#     incident, acked, next_action = _handle(incident_service.get_incident_status, db, incident_id)
#     return IncidentStatusResponse(
#         incident_id=incident.id,
#         state=incident.status,
#         next_action=next_action,
#         acknowledged_by=[AckEntry(target_type=r.target_type, at=r.ack_time) for r in acked],
#     )


# @incidents_router.post("/{incident_id}/media", response_model=MediaAttachResponse)
# def attach_media(incident_id: uuid.UUID, payload: MediaAttachRequest, db: Session = Depends(get_db)):
#     media_id = _handle(incident_service.attach_media, db, incident_id, payload)
#     return MediaAttachResponse(incident_id=incident_id, media_id=media_id, status="attached")


# @incidents_router.post("/{incident_id}/ack", response_model=AckResponse)
# def ack_incident(incident_id: uuid.UUID, payload: AckRequest, db: Session = Depends(get_db)):
#     incident = _handle(incident_service.record_ack, db, incident_id, payload)
#     return AckResponse(incident_id=incident.id, status="ack_recorded")


"""Module 21 — API Layer: SOS / Incidents. Thin controllers only; logic in Module 8-11/18 services.

Bug #9 FIX APPLIED (SECURITY): trigger_sos() had no Depends(get_current_user) at all —
anyone could POST /v1/sos with no Authorization header and create an incident "as" any
user_id in the request body. Fixed by requiring authentication and rejecting any request
where payload.user_id doesn't match the authenticated caller's own id.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.incident import (
    SOSRequest, SOSResponse, TargetStatus, SafeZoneInfo,
    IncidentDetailResponse, RiskState, RoutingInfo, IncidentSafeZone, IncidentTimestamps,
    IncidentStatusResponse, AckEntry,
    MediaAttachRequest, MediaAttachResponse,
    AckRequest, AckResponse,
)
from app.services import incident_service

sos_router = APIRouter(prefix="/v1/sos", tags=["sos"])
incidents_router = APIRouter(prefix="/v1/incidents", tags=["incidents"])


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@sos_router.post("", response_model=SOSResponse, status_code=status.HTTP_201_CREATED)
def trigger_sos(
    payload: SOSRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Bug #9 — the authenticated caller may only trigger an SOS as themselves.
    if payload.user_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "user_id in request body must match the authenticated user",
        )

    incident, result, safe_zone = _handle(incident_service.create_sos, db, payload)
    return SOSResponse(
        incident_id=incident.id,
        status=incident.status,
        location_locked=True,
        ack_timeout_sec=result["ack_timeout_sec"],
        primary_targets=[TargetStatus(**t) for t in result["primary_targets"]],
        # compute_safezone_guidance() (app/services/safezone_service.py) returns a plain
        # dict, not an object — .__dict__ would raise AttributeError. Real dict keys are
        # safe_zone_name / distance_m / eta_minutes; mapped explicitly to SafeZoneInfo's
        # name / distance_m / eta_min_walk (verified against the real function's return).
        safe_zone=SafeZoneInfo(
            name=safe_zone["safe_zone_name"],
            distance_m=safe_zone["distance_m"],
            eta_min_walk=safe_zone["eta_minutes"],
        ) if safe_zone else None,
        message="Help has been alerted. Stay near your location and follow safe-zone guidance.",
    )


@incidents_router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident(incident_id: uuid.UUID, db: Session = Depends(get_db)):
    incident, safe_zone, authority, hospital, primary = _handle(incident_service.get_incident, db, incident_id)
    return IncidentDetailResponse(
        incident_id=incident.id,
        status=incident.status,
        incident_type=incident.incident_type,
        severity=incident.severity,
        current_location={"lat": float(incident.lat), "lng": float(incident.lng)},
        risk_state=RiskState(
            beach_verdict=incident.current_hazard_context.get("current_verdict"),
            hazards=incident.current_hazard_context.get("alert_flags", []),
            eta_minutes=incident.current_hazard_context.get("eta_minutes"),
        ),
        routing=RoutingInfo(
            primary_authority=authority.target_name if authority else None,
            hospital=hospital.target_name if hospital else None,
            contact_status=primary.ack_status if primary else None,
        ),
        # get_active_guidance() (app/services/safezone_service.py) returns a plain dict —
        # keys are safe_zone_name / eta_minutes (after the JOIN fix applied there), not
        # .name / .eta_min_walk attributes on an object.
        safe_zone=IncidentSafeZone(
            name=safe_zone["safe_zone_name"],
            route_eta_min=safe_zone["eta_minutes"],
        ) if safe_zone else None,
        timestamps=IncidentTimestamps(created_at=incident.created_at, last_update=incident.updated_at),
    )


@incidents_router.get("/{incident_id}/status", response_model=IncidentStatusResponse)
def get_incident_status(incident_id: uuid.UUID, db: Session = Depends(get_db)):
    incident, acked, next_action = _handle(incident_service.get_incident_status, db, incident_id)
    return IncidentStatusResponse(
        incident_id=incident.id,
        state=incident.status,
        next_action=next_action,
        acknowledged_by=[AckEntry(target_type=r.target_type, at=r.ack_time) for r in acked],
    )


@incidents_router.post("/{incident_id}/media", response_model=MediaAttachResponse)
def attach_media(incident_id: uuid.UUID, payload: MediaAttachRequest, db: Session = Depends(get_db)):
    media_id = _handle(incident_service.attach_media, db, incident_id, payload)
    return MediaAttachResponse(incident_id=incident_id, media_id=media_id, status="attached")


@incidents_router.post("/{incident_id}/ack", response_model=AckResponse)
def ack_incident(incident_id: uuid.UUID, payload: AckRequest, db: Session = Depends(get_db)):
    incident = _handle(incident_service.record_ack, db, incident_id, payload)
    return AckResponse(incident_id=incident.id, status="ack_recorded")