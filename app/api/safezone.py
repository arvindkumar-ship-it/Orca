from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.safezone import SafeZoneComputeRequest, SafeZoneRecomputeRequest, SafeRouteResponse
from app.services import safezone_service

router = APIRouter(prefix="/safezone", tags=["safezone"])


@router.post("/guidance", response_model=SafeRouteResponse, status_code=201)
def compute_guidance(body: SafeZoneComputeRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return safezone_service.compute_safezone_guidance(
            db, str(user.id), body.lat, body.lng, body.beach_id, body.incident_report_id, body.trip_plan_id, "initial",
        )
    except ValueError as e:
        if str(e) == "NO_SAFE_ZONE_FOUND_IN_RADIUS":
            raise HTTPException(404, "No safe zone found within search radius")
        raise HTTPException(500, "Failed to compute safe-zone guidance")


@router.post("/guidance/{guidance_id}/recompute", response_model=SafeRouteResponse)
def recompute(guidance_id: str, body: SafeZoneRecomputeRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return safezone_service.recompute_guidance(db, guidance_id, body.lat, body.lng, body.reason)
    except ValueError:
        raise HTTPException(404, "Guidance not found")


@router.get("/guidance/active")
def get_active(incident_report_id: str | None = Query(default=None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    guidance = safezone_service.get_active_guidance(db, str(user.id), incident_report_id)
    if not guidance:
        raise HTTPException(404, "No active guidance found")
    return guidance


@router.post("/guidance/{guidance_id}/share")
def share(guidance_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        queued = safezone_service.share_guidance(db, guidance_id, str(user.id))
        return {"contacts_notified": queued}
    except ValueError:
        raise HTTPException(404, "Guidance not found")
