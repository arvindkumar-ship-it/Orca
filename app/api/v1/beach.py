# # MODULE 19: API Layer — Beaches, Risk, Forecast — API Router
# # Mounted at /v1 — public read endpoints, no auth required (safety data must be
# # viewable pre-login, e.g. pre-check journey from Module 0). Rate-limited via
# # shared slowapi limiter (core.rate_limit), consistent with other public routers.

# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.db import get_db
# from app.core.rate_limit import limiter
# from app.schemas.beach import BeachSearchResponse, BeachDetail, RiskResponse, ForecastResponse, AlertsResponse
# from app.services import beach_service as svc

# router = APIRouter(prefix="/v1", tags=["beaches"])


# def _parse_near(near: str | None) -> tuple[float, float] | None:
#     if not near:
#         return None
#     try:
#         lat_str, lng_str = near.split(",")
#         return float(lat_str), float(lng_str)
#     except ValueError:
#         return None


# @router.get("/beaches", response_model=BeachSearchResponse)
# @limiter.limit("120/minute")
# async def get_beaches(
#     state: str | None = None,
#     near: str | None = None,
#     radius_m: int | None = None,
#     activity: str | None = None,
#     db: AsyncSession = Depends(get_db),
# ):
#     items = await svc.search_beaches(db, state, _parse_near(near), radius_m, activity)
#     return BeachSearchResponse(items=items)


# @router.get("/beaches/{beach_id}", response_model=BeachDetail)
# @limiter.limit("120/minute")
# async def get_beach_by_id(beach_id: str, db: AsyncSession = Depends(get_db)):
#     detail = await svc.get_beach_detail(db, beach_id)
#     if not detail:
#         raise HTTPException(status_code=404, detail="beach not found")
#     return detail


# @router.get("/beaches/{beach_id}/risk", response_model=RiskResponse)
# @limiter.limit("120/minute")
# async def get_beach_risk(
#     beach_id: str, activity: str = "swimming", db: AsyncSession = Depends(get_db)
# ):
#     return await svc.get_beach_risk(db, beach_id, activity)


# @router.get("/beaches/{beach_id}/forecast", response_model=ForecastResponse)
# @limiter.limit("120/minute")
# async def get_beach_forecast(
#     beach_id: str, activity: str = "swimming", hours: int = 24, db: AsyncSession = Depends(get_db)
# ):
#     items = await svc.get_beach_forecast(db, beach_id, activity, hours)
#     return ForecastResponse(beach_id=beach_id, items=items)


# @router.get("/alerts", response_model=AlertsResponse)
# @limiter.limit("120/minute")
# async def get_alerts(
#     near: str = Query(..., description="lat,lng"),
#     radius_m: int = 50000,
#     db: AsyncSession = Depends(get_db),
# ):
#     parsed = _parse_near(near)
#     if not parsed:
#         raise HTTPException(status_code=400, detail="near=lat,lng required")
#     lat, lng = parsed
#     items = await svc.get_active_alerts(db, lat, lng, radius_m)
#     return AlertsResponse(items=items)


# MODULE 19: API Layer — Beaches, Risk, Forecast — API Router
# Mounted at /v1 — public read endpoints, no auth required (safety data must be
# viewable pre-login, e.g. pre-check journey from Module 0). Rate-limited via
# shared slowapi limiter (core.rate_limit), consistent with other public routers.
#
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.
#
# ⚠️ FIX APPLIED (not part of B1, but blocking): slowapi's @limiter.limit(...) decorator
# requires a `request: Request` parameter on every decorated route handler — it reads
# request.state internally to track per-client counts. None of the original handlers had
# it, which would make every one of these rate limits silently no-op (or error, depending
# on slowapi version). Added `request: Request` to all four routes below.

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from app.schemas.beach import BeachSearchResponse, BeachDetail, RiskResponse, ForecastResponse, AlertsResponse
from app.services import beach_service as svc

router = APIRouter(prefix="/v1", tags=["beaches"])


def _parse_near(near: str | None) -> tuple[float, float] | None:
    if not near:
        return None
    try:
        lat_str, lng_str = near.split(",")
        return float(lat_str), float(lng_str)
    except ValueError:
        return None


@router.get("/beaches", response_model=BeachSearchResponse)
@limiter.limit("120/minute")
def get_beaches(
    request: Request,
    state: str | None = None,
    near: str | None = None,
    radius_m: int | None = None,
    activity: str | None = None,
    db: Session = Depends(get_db),
):
    items = svc.search_beaches(db, state, _parse_near(near), radius_m, activity)
    return BeachSearchResponse(items=items)


@router.get("/beaches/{beach_id}", response_model=BeachDetail)
@limiter.limit("120/minute")
def get_beach_by_id(request: Request, beach_id: str, db: Session = Depends(get_db)):
    detail = svc.get_beach_detail(db, beach_id)
    if not detail:
        raise HTTPException(status_code=404, detail="beach not found")
    return detail


@router.get("/beaches/{beach_id}/risk", response_model=RiskResponse)
@limiter.limit("120/minute")
def get_beach_risk(
    request: Request, beach_id: str, activity: str = "swimming", db: Session = Depends(get_db)
):
    return svc.get_beach_risk(db, beach_id, activity)


@router.get("/beaches/{beach_id}/forecast", response_model=ForecastResponse)
@limiter.limit("120/minute")
def get_beach_forecast(
    request: Request, beach_id: str, activity: str = "swimming", hours: int = 24, db: Session = Depends(get_db)
):
    items = svc.get_beach_forecast(db, beach_id, activity, hours)
    return ForecastResponse(beach_id=beach_id, items=items)


@router.get("/alerts", response_model=AlertsResponse)
@limiter.limit("120/minute")
def get_alerts(
    request: Request,
    near: str = Query(..., description="lat,lng"),
    radius_m: int = 50000,
    db: Session = Depends(get_db),
):
    parsed = _parse_near(near)
    if not parsed:
        raise HTTPException(status_code=400, detail="near=lat,lng required")
    lat, lng = parsed
    items = svc.get_active_alerts(db, lat, lng, radius_m)
    return AlertsResponse(items=items)