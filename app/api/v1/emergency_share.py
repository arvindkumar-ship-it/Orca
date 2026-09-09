"""Module 22 — API Layer: Emergency Sharing."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.emergency_share import (
    ShareStartRequest, ShareStartResponse, SharedTarget,
    ShareStopResponse, ShareSessionResponse,
)
from app.services import emergency_share_service as svc

router = APIRouter(prefix="/v1/emergency/share", tags=["emergency-share"])


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


def _to_targets(session) -> list[SharedTarget]:
    return [SharedTarget(contact_id=t.contact_id, status=t.status) for t in session.targets]


@router.post("/start", response_model=ShareStartResponse, status_code=status.HTTP_201_CREATED)
def start_share(payload: ShareStartRequest, db: Session = Depends(get_db)):
    session = _handle(svc.start_share, db, payload)
    return ShareStartResponse(share_session_id=session.id, status=session.status, shared_with=_to_targets(session))


@router.post("/stop", response_model=ShareStopResponse)
def stop_share(share_session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = _handle(svc.stop_share, db, share_session_id)
    return ShareStopResponse(share_session_id=session.id, status=session.status)


@router.get("/{share_session_id}", response_model=ShareSessionResponse)
def get_share(share_session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = _handle(svc.get_share, db, share_session_id)
    return ShareSessionResponse(
        share_session_id=session.id,
        incident_id=session.incident_report_id,
        status=session.status,
        share_live_location=session.share_live_location,
        share_route=session.share_route,
        shared_with=_to_targets(session),
    )
