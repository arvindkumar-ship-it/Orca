"""ORCA — GENERALIZE of app/api/v1/beach.py -> zones router.
Same APIRouter(prefix="/v1"), slowapi limiter, request: Request pattern,
same _parse_near() helper shape."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.services import zone_service

router = APIRouter(prefix="/v1", tags=["zones"])


def _parse_near(near: str | None) -> tuple[float, float] | None:
    if not near:
        return None
    try:
        lat_s, lng_s = near.split(",")
        return float(lat_s), float(lng_s)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="near must be 'lat,lng'")


@router.get("/zones")
@limiter.limit("120/minute")
def list_zones(
    request: Request,
    state: str | None = None,
    zone_type: str | None = Query(None, description="fishing_zone | open_sea_sector | coastal_beach"),
    near: str | None = Query(None, description="'lat,lng'"),
    radius_m: int | None = None,
    activity: str | None = None,
    db: Session = Depends(get_db),
):
    return zone_service.search_zones(db, state, _parse_near(near), radius_m, activity, zone_type)


@router.get("/zones/{zone_id}")
@limiter.limit("120/minute")
def zone_detail(zone_id: str, request: Request, db: Session = Depends(get_db)):
    detail = zone_service.get_zone_detail(db, zone_id)
    if not detail:
        raise HTTPException(status_code=404, detail="zone not found")
    return detail


@router.get("/zones/{zone_id}/risk")
@limiter.limit("120/minute")
def zone_risk(zone_id: str, activity_type: str, request: Request, db: Session = Depends(get_db)):
    return zone_service.get_zone_risk(db, zone_id, activity_type)


@router.get("/zones/{zone_id}/forecast")
@limiter.limit("120/minute")
def zone_forecast(zone_id: str, activity_type: str, request: Request, hours: int = 24, db: Session = Depends(get_db)):
    return zone_service.get_zone_forecast(db, zone_id, activity_type, hours)


@router.get("/alerts")
@limiter.limit("120/minute")
def active_alerts(lat: float, lng: float, request: Request, radius_m: int = 25000, db: Session = Depends(get_db)):
    return zone_service.get_active_alerts(db, lat, lng, radius_m)
