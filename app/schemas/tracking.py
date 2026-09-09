from typing import Optional
from pydantic import BaseModel


class StartTrackingRequest(BaseModel):
    incident_report_id: str


class IngestPingRequest(BaseModel):
    lat: float
    lng: float
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    heading: Optional[float] = None
    battery_pct: Optional[int] = None
    signal_strength: Optional[str] = None
    source: str = "gps"


class UpdateStatusRequest(BaseModel):
    status: str


class StopTrackingRequest(BaseModel):
    reason: str = "manual_stop"


class TrackingSnapshot(BaseModel):
    session_id: str
    incident_report_id: str
    status: str
    tracking_mode: str
    last_ping: Optional[dict] = None
    hospital_eta_minutes: Optional[float] = None
    safe_zone_eta_minutes: Optional[float] = None
    responder_eta_minutes: Optional[float] = None
