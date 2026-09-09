# # MODULE 17: Admin Console — Schemas

# from typing import Any, Literal, Optional

# from pydantic import BaseModel


# class BeachUpsertInput(BaseModel):
#     id: Optional[str] = None
#     name: str
#     state: str
#     district: Optional[str] = None
#     coast_region: Optional[str] = None
#     geom_geojson: dict[str, Any]  # GeoJSON Polygon
#     has_lifeguard: bool = False
#     public_access: bool = True
#     active: bool = True


# class ActivityThresholdInput(BaseModel):
#     beach_id: str
#     activity_type: str
#     min_safe_wave_height: Optional[float] = None
#     max_safe_wave_height: Optional[float] = None
#     min_safe_wind_speed: Optional[float] = None
#     max_safe_wind_speed: Optional[float] = None
#     rip_current_risk_cutoff: Optional[float] = None


# class JurisdictionUpsertInput(BaseModel):
#     id: Optional[str] = None
#     name: str
#     authority_type: str
#     contact_phone: Optional[str] = None
#     contact_email: Optional[str] = None
#     service_area_geom_geojson: dict[str, Any]  # GeoJSON MultiPolygon
#     escalation_level: int = 1
#     active: bool = True


# class HospitalUpsertInput(BaseModel):
#     id: Optional[str] = None
#     name: str
#     type: str
#     lat: float
#     lng: float
#     contact_phone: Optional[str] = None
#     contact_email: Optional[str] = None
#     capabilities: dict[str, bool] = {}
#     capacity_status: str = "unknown"
#     active: bool = True


# class IncidentReviewFilters(BaseModel):
#     status: Optional[str] = None
#     incident_type: Optional[str] = None
#     beach_id: Optional[str] = None
#     from_: Optional[str] = None
#     to: Optional[str] = None
#     page: int = 1
#     page_size: int = 25


# class AckReviewRow(BaseModel):
#     incident_id: str
#     target_type: str
#     target_id: str
#     dispatched_at: str
#     acked_at: Optional[str] = None
#     ack_latency_s: Optional[float] = None
#     escalated: bool


# class ResponseLatencyMetrics(BaseModel):
#     window: str
#     mean_dispatch_to_ack_s: float
#     p50_s: float
#     p90_s: float
#     p99_s: float
#     escalation_rate: float
#     sample_size: int


# class RiskRuleUpdateInput(BaseModel):
#     rule_id: str
#     parameter: str
#     new_value: float
#     reason: str  # mandatory justification, stored in audit


# class LogExportRequest(BaseModel):
#     entity_type: Literal["audit_events", "incident_reports", "notification_queue"]
#     from_: str
#     to: str
#     format: Literal["csv", "json"] = "json"





# MODULE 17: Admin Console — Schemas

from typing import Any, Literal, Optional

from pydantic import BaseModel


class BeachUpsertInput(BaseModel):
    id: Optional[str] = None
    name: str
    state: str
    district: Optional[str] = None
    coast_region: Optional[str] = None
    geom_geojson: dict[str, Any]  # GeoJSON Polygon
    has_lifeguard: bool = False
    public_access: bool = True
    active: bool = True


class ActivityThresholdInput(BaseModel):
    beach_id: str
    activity_type: str
    min_safe_wave_height: Optional[float] = None
    max_safe_current_speed: Optional[float] = None
    max_safe_wind_speed: Optional[float] = None
    max_safe_swell: Optional[float] = None
    water_quality_min: Optional[float] = None
    tide_sensitivity: Optional[float] = None
    risk_weights: Optional[dict[str, Any]] = None


class SafeZoneUpsertInput(BaseModel):
    beach_id: str
    name: str
    geom_geojson: dict[str, Any]
    elevation_m: Optional[float] = None
    route_notes: Optional[str] = None


class JurisdictionUpsertInput(BaseModel):
    id: Optional[str] = None
    name: str
    authority_type: str
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    service_area_geom_geojson: dict[str, Any]  # GeoJSON MultiPolygon
    escalation_level: int = 1
    active: bool = True


class HospitalUpsertInput(BaseModel):
    id: Optional[str] = None
    name: str
    type: str
    lat: float
    lng: float
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    capabilities: dict[str, bool] = {}
    capacity_status: str = "unknown"
    active: bool = True


class IncidentReviewFilters(BaseModel):
    status: Optional[str] = None
    incident_type: Optional[str] = None
    beach_id: Optional[str] = None
    from_: Optional[str] = None
    to: Optional[str] = None
    page: int = 1
    page_size: int = 25


class AckReviewRow(BaseModel):
    incident_id: str
    target_type: str
    target_id: str
    dispatched_at: str
    acked_at: Optional[str] = None
    ack_latency_s: Optional[float] = None
    escalated: bool


class ResponseLatencyMetrics(BaseModel):
    window: str
    mean_dispatch_to_ack_s: float
    p50_s: float
    p90_s: float
    p99_s: float
    escalation_rate: float
    sample_size: int


class RiskRuleUpdateInput(BaseModel):
    rule_id: str
    parameter: str
    new_value: float
    reason: str  # mandatory justification, stored in audit


class LogExportRequest(BaseModel):
    entity_type: Literal["audit_events", "incident_reports", "notification_queue"]
    from_: str
    to: str
    format: Literal["csv", "json"] = "json"


# --- B11: OTP/auth schemas, ported over from Module 20-26's admin.py (auth_router part) ---
import uuid


class OTPRequest(BaseModel):
    phone: str


class OTPRequestResponse(BaseModel):
    phone: str
    status: str
    expires_in_sec: int


class OTPVerify(BaseModel):
    phone: str
    code: str


class OTPVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID


class LogoutResponse(BaseModel):
    status: str = "logged_out"