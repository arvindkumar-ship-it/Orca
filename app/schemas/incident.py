import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Location(BaseModel):
    lat: float
    lng: float
    accuracy_m: Optional[float] = None
    source: str = "gps"  # gps|network|last_known


class HazardContext(BaseModel):
    current_verdict: Optional[str] = None
    alert_flags: List[str] = Field(default_factory=list)
    eta_minutes: Optional[int] = None


class DeviceState(BaseModel):
    battery_pct: Optional[int] = None
    signal_strength: Optional[str] = None
    offline: bool = False


class MediaItem(BaseModel):
    type: str
    url: str
    caption: Optional[str] = None


class SOSRequest(BaseModel):
    user_id: uuid.UUID
    device_id: Optional[uuid.UUID] = None
    trigger_type: str  # manual|long_press|shake|voice|auto
    incident_type: str
    severity: str  # low|medium|high|critical
    beach_id: Optional[uuid.UUID] = None
    activity_type: Optional[str] = None
    location: Location
    hazard_context: HazardContext = HazardContext()
    device_state: DeviceState = DeviceState()
    contacts: List[uuid.UUID] = Field(default_factory=list)
    media: List[MediaItem] = Field(default_factory=list)
    notes: Optional[str] = None


class TargetStatus(BaseModel):
    type: str
    name: str
    status: str


class SafeZoneInfo(BaseModel):
    name: str
    distance_m: float
    eta_min_walk: float


class SOSResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    location_locked: bool
    ack_timeout_sec: int
    primary_targets: List[TargetStatus]
    safe_zone: Optional[SafeZoneInfo] = None
    message: str


class RiskState(BaseModel):
    beach_verdict: Optional[str] = None
    hazards: List[str] = Field(default_factory=list)
    eta_minutes: Optional[int] = None


class RoutingInfo(BaseModel):
    primary_authority: Optional[str] = None
    hospital: Optional[str] = None
    contact_status: Optional[str] = None


class IncidentSafeZone(BaseModel):
    name: str
    route_eta_min: float


class IncidentTimestamps(BaseModel):
    created_at: datetime
    last_update: datetime


class IncidentDetailResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    incident_type: str
    severity: str
    current_location: dict
    risk_state: RiskState
    routing: RoutingInfo
    safe_zone: Optional[IncidentSafeZone] = None
    timestamps: IncidentTimestamps


class AckEntry(BaseModel):
    target_type: str
    at: datetime


class IncidentStatusResponse(BaseModel):
    incident_id: uuid.UUID
    state: str
    next_action: str
    acknowledged_by: List[AckEntry]


class MediaAttachRequest(BaseModel):
    type: str  # photo|video|voice_note
    url: str
    caption: Optional[str] = None


class MediaAttachResponse(BaseModel):
    incident_id: uuid.UUID
    media_id: uuid.UUID
    status: str


class AckRequest(BaseModel):
    target_type: str  # 112|hospital|authority
    target_name: str
    ack_status: str  # received|accepted|rejected|unable
    external_ref: Optional[str] = None


class AckResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
