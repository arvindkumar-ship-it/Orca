"""ORCA — NEW router: route optimization (R9)."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.services import geofence_service
from route_optimizer.optimizer import find_safe_route
from route_optimizer.risk_window import compute_cell_risk
from route_optimizer.advisory import generate_route_advisory

router = APIRouter(prefix="/v1", tags=["route"])


class RouteRequest(BaseModel):
    origin_lat: float = Field(ge=-90, le=90)
    origin_lng: float = Field(ge=-180, le=180)
    dest_lat: float = Field(ge=-90, le=90)
    dest_lng: float = Field(ge=-180, le=180)
    activity_type: str = "fishing"
    window_start: datetime
    window_end: datetime


@router.post("/route/plan")
@limiter.limit("30/minute")  # route planning is compute-heavy (grid search) — tighter limit than read endpoints
def plan_route(payload: RouteRequest, request: Request, db: Session = Depends(get_db)):
    result = find_safe_route(
        db, (payload.origin_lat, payload.origin_lng), (payload.dest_lat, payload.dest_lng),
        payload.activity_type, payload.window_start, payload.window_end,
    )
    if not result["feasible"]:
        return {**result, "advisory": "No safe route found avoiding restricted zones — consider a different destination or time window."}

    geofence_result = geofence_service.check_route(
        db, "LINESTRING(" + ", ".join(f"{lng} {lat}" for lat, lng in result["path"]) + ")"
    )
    worst_cell = compute_cell_risk(db, payload.dest_lat, payload.dest_lng, payload.activity_type,
                                    payload.window_start, payload.window_end)
    advisory = generate_route_advisory(worst_cell, geofence_result, alternative_available=False)

    return {**result, "geofence": geofence_result, "advisory": advisory}
