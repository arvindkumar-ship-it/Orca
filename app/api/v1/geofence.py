"""
ORCA — NEW router: geofence checks (R8).

Mounted the same way WaveSafe mounts beach.py: APIRouter(prefix="/v1",
tags=[...]), slowapi limiter singleton, every handler takes request: Request
(WaveSafe's beach.py header explicitly documents this as a required gotcha —
the limiter decorator silently no-ops without it).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.services import geofence_service

router = APIRouter(prefix="/v1", tags=["geofence"])


class GeofencePointCheck(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class GeofenceRouteCheck(BaseModel):
    route_wkt: str  # e.g. "LINESTRING(72.8 18.9, 72.9 19.0, ...)"


@router.post("/geofence/check-point")
@limiter.limit("120/minute")
def check_point(payload: GeofencePointCheck, request: Request, db: Session = Depends(get_db)):
    return geofence_service.check_point(db, payload.lat, payload.lng)


@router.post("/geofence/check-route")
@limiter.limit("60/minute")
def check_route(payload: GeofenceRouteCheck, request: Request, db: Session = Depends(get_db)):
    return geofence_service.check_route(db, payload.route_wkt)
