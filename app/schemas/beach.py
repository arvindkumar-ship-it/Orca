# MODULE 19: API Layer — Beaches, Risk, Forecast — Schemas

from typing import Any, Literal, Optional

from pydantic import BaseModel


class BeachSearchItem(BaseModel):
    id: str
    name: str
    state: str
    district: Optional[str] = None
    distance_m: Optional[int] = None
    has_lifeguard: bool
    current_verdict: Optional[str] = None
    current_risk_score: Optional[float] = None


class BeachSearchResponse(BaseModel):
    items: list[BeachSearchItem]


class SafeZoneRef(BaseModel):
    id: str
    name: str
    distance_m: int


class JurisdictionRef(BaseModel):
    id: str
    name: str


class BeachDetail(BaseModel):
    id: str
    name: str
    state: str
    district: Optional[str] = None
    geom: dict[str, Any]
    has_lifeguard: bool
    public_access: bool
    safe_zones: list[SafeZoneRef]
    jurisdiction: Optional[JurisdictionRef] = None


class RiskExplanation(BaseModel):
    top_factors: list[str]


class RiskResponse(BaseModel):
    beach_id: str
    activity_type: str
    forecast_time: str
    risk_score: float
    verdict: Literal["safe", "caution", "unsafe"]
    hard_override_reason: Optional[str] = None
    explanation: RiskExplanation


class ForecastItem(BaseModel):
    forecast_time: str
    wave_height: float
    current_speed: float
    wind_speed: float
    risk_score: float
    verdict: str


class ForecastResponse(BaseModel):
    beach_id: str
    items: list[ForecastItem]


class AlertItem(BaseModel):
    id: str
    alert_type: str
    severity: str
    title: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None


class AlertsResponse(BaseModel):
    items: list[AlertItem]
