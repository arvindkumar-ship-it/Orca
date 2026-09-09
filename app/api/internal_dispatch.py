"""
Module 25 addition — /internal/router/escalate and /internal/router/dispatch,
now backed by Module 27's DispatchStateMachine instead of raw status writes.
Guarded by internal API key (verify_internal_key), not JWT — same as rest of Module 25.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_internal_key
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine

router = APIRouter(prefix="/internal/router", tags=["internal-dispatch"])


class TransitionRequest(BaseModel):
    incident_id: uuid.UUID
    to_state: IncidentState
    reason: str | None = None


class TransitionResponse(BaseModel):
    incident_id: uuid.UUID
    status: IncidentState


@router.post(
    "/dispatch",
    response_model=TransitionResponse,
    dependencies=[Depends(verify_internal_key)],
)
def dispatch_incident(body: TransitionRequest, db: Session = Depends(get_db)):
    """
    Called by authority_router/hospital_router (Modules 0-19) once the
    incident packet is built and targets are picked. Drives created -> ...
    -> dispatched in one call chain; each intermediate hop is still a
    validated transition so history/audit stay complete (Module 33 rule:
    never store incident without status history).
    """
    sm = DispatchStateMachine(db)
    try:
        result = sm.transition(
            body.incident_id,
            body.to_state,
            actor_type="internal_service",
            reason=body.reason or "internal_router_dispatch",
        )
        db.commit()
    except InvalidTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return TransitionResponse(incident_id=body.incident_id, status=result)


@router.post(
    "/escalate",
    response_model=TransitionResponse,
    dependencies=[Depends(verify_internal_key)],
)
def escalate_incident(body: TransitionRequest, db: Session = Depends(get_db)):
    """
    Manual/forced escalation trigger (used by escalation_worker's failure
    path or an ops action outside the automatic timer). Same graph as the
    automatic path — this is not a side-door, it goes through the same
    DispatchStateMachine.transition() validation.
    """
    sm = DispatchStateMachine(db)
    try:
        current = sm.get_current_state(body.incident_id)
        if body.to_state not in {
            IncidentState.TIMEOUT,
            IncidentState.ESCALATED,
            IncidentState.FALLBACK_112,
            IncidentState.MANUAL_OPS,
        }:
            raise HTTPException(
                status_code=400,
                detail="escalate endpoint only accepts escalation-branch states",
            )
        result = sm.transition(
            body.incident_id,
            body.to_state,
            actor_type="internal_service",
            reason=body.reason or "manual_escalation",
        )
        db.commit()
    except InvalidTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return TransitionResponse(incident_id=body.incident_id, status=result)


@router.get(
    "/incident/{incident_id}/status",
    response_model=TransitionResponse,
    dependencies=[Depends(verify_internal_key)],
)
def get_incident_status(incident_id: uuid.UUID, db: Session = Depends(get_db)):
    sm = DispatchStateMachine(db)
    try:
        current = sm.get_current_state(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return TransitionResponse(incident_id=incident_id, status=current)
