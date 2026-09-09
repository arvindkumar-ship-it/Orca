"""ORCA — GENERALIZE router for safe_harbor_service.py, mirrors zones.py's pattern."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.services import safe_harbor_service

router = APIRouter(prefix="/v1", tags=["safe_harbors"])


class SafeHarborRequest(BaseModel):
    lat: float
    lng: float
    marine_zone_id: str | None = None
    incident_report_id: str | None = None


@router.post("/safe-harbors/guidance")
@limiter.limit("60/minute")
def get_guidance(payload: SafeHarborRequest, request: Request, db: Session = Depends(get_db)):
    return safe_harbor_service.compute_safe_harbor_guidance(
        db, user_id=None, lat=payload.lat, lng=payload.lng,
        marine_zone_id=payload.marine_zone_id, incident_report_id=payload.incident_report_id,
        trigger_reason="manual_request",
    )
