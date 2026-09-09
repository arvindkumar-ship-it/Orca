"""ORCA — NEW: app/api/v1/ocean.py. Standalone REST front for
agents/ocean_analytics_agent.py — closes the gap flagged in
frontend/src/services/fishingZones.js and PROGRESS.md pass 6."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.rate_limit import limiter
from agents.ocean_analytics_agent import find_nearest_pfz, get_sst_chlorophyll_hotspots

router = APIRouter(prefix="/v1", tags=["ocean"])


@router.get("/ocean/pfz")
@limiter.limit("120/minute")
def nearest_pfz(lat: float, lng: float, request: Request, db: Session = Depends(get_db)):
    return find_nearest_pfz(db, lat, lng).to_dict()


@router.get("/ocean/hotspots")
@limiter.limit("60/minute")
def hotspots(min_lat: float, min_lng: float, max_lat: float, max_lng: float, request: Request,
             product: str = "chlorophyll", db: Session = Depends(get_db)):
    return get_sst_chlorophyll_hotspots(db, min_lat, min_lng, max_lat, max_lng, product).to_dict()
