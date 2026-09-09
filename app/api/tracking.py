from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user, get_current_admin
from app.schemas.tracking import StartTrackingRequest, IngestPingRequest, UpdateStatusRequest, StopTrackingRequest
from app.services import tracking_service

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post("/sessions", status_code=201)
def start(body: StartTrackingRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sid = tracking_service.start_tracking(db, body.incident_report_id, str(user.id))
    return {"session_id": sid, "status": "awaiting_acknowledgment"}


@router.post("/sessions/{session_id}/ping", status_code=202)
def ping(session_id: str, body: IngestPingRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        tracking_service.ingest_ping(db, session_id, body)
        return {"status": "ping_recorded"}
    except ValueError as e:
        if str(e) == "SESSION_NOT_FOUND":
            raise HTTPException(404, "Session not found")
        raise HTTPException(409, "Session already ended")


@router.get("/sessions/{session_id}")
def snapshot(session_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return tracking_service.get_snapshot(db, session_id)
    except ValueError:
        raise HTTPException(404, "Session not found")


@router.patch("/sessions/{session_id}/status")
def patch_status(session_id: str, body: UpdateStatusRequest, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        tracking_service.update_status(db, session_id, body.status, "operator", str(admin.id))
        return {"session_id": session_id, "status": body.status}
    except ValueError:
        raise HTTPException(404, "Session not found or already ended")


@router.post("/sessions/{session_id}/stop")
def stop(session_id: str, body: StopTrackingRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        tracking_service.stop_tracking(db, session_id, body.reason, str(user.id))
        return {"session_id": session_id, "status": "stopped"}
    except ValueError:
        raise HTTPException(404, "Session not found or already ended")
