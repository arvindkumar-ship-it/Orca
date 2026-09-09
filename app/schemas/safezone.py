from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class SafeZoneComputeRequest(BaseModel):
    lat: float
    lng: float
    beach_id: Optional[str] = None
    incident_report_id: Optional[str] = None
    trip_plan_id: Optional[str] = None


class SafeZoneRecomputeRequest(BaseModel):
    lat: float
    lng: float
    reason: str = Field(default="user_moved", pattern="^(hazard_update|user_moved)$")


class SafeRouteResponse(BaseModel):
    guidance_id: str
    safe_zone_id: str
    safe_zone_name: str
    route_geojson: Any
    distance_m: float
    eta_minutes: float
    route_score: float
    instruction: str
    warnings: list[str]
    hazard_alert_ids: list[str]
    computed_at: datetime
    trigger_reason: str

    class Config:
        from_attributes = True
