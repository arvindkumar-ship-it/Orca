"""ORCA — Pydantic schemas for zones (GENERALIZE of app/schemas/beach.py)."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ZoneSearchItem(BaseModel):
    id: str
    name: str
    zone_type: str
    state: str
    district: Optional[str] = None
    distance_m: Optional[int] = None
    depth_m: Optional[float] = None
    current_verdict: Optional[str] = None
    current_risk_score: Optional[float] = None


class SafeHarborRef(BaseModel):
    id: str
    name: str
    distance_m: int


class JurisdictionRef(BaseModel):
    id: str
    name: str


class ZoneDetail(BaseModel):
    id: str
    name: str
    zone_type: str
    state: str
    district: Optional[str] = None
    geom: dict[str, Any]
    depth_m: Optional[float] = None
    public_access: bool
    safe_harbors: list[SafeHarborRef]
    jurisdiction: Optional[JurisdictionRef] = None


class RiskExplanation(BaseModel):
    top_factors: list[Any] = []


class RiskResponse(BaseModel):
    zone_id: str
    activity_type: str
    forecast_time: Optional[datetime] = None
    risk_score: Optional[float] = None
    verdict: Optional[str] = None
    hard_override_reason: Optional[str] = None
    explanation: RiskExplanation


class ForecastItem(BaseModel):
    forecast_time: Optional[datetime] = None
    wave_height: Optional[float] = None
    current_speed: Optional[float] = None
    wind_speed: Optional[float] = None
    risk_score: Optional[float] = None
    verdict: Optional[str] = None


class AlertItem(BaseModel):
    id: Any
    alert_type: str
    severity: str
    title: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
