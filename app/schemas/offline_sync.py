# MODULE 16: Offline-First Engineering — Schemas
# Migrated from Node/Express+TS -> FastAPI+Pydantic to match finalized project stack.

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class SyncBundleQuery(BaseModel):
    beach_ids: list[str] = []
    last_synced_at: Optional[datetime] = None
    device_id: str


class StampedRecord(BaseModel):
    data: dict[str, Any]
    server_version: int
    cached_at: datetime
    stale_after_s: int


class SyncBundleResponse(BaseModel):
    synced_at: datetime
    beach_risk_snapshots: list[StampedRecord] = []
    trip_plan: Optional[StampedRecord] = None
    safe_zones: list[StampedRecord] = []
    emergency_contacts: list[StampedRecord] = []
    authority_directory: list[StampedRecord] = []
    hospital_directory: list[StampedRecord] = []
    alert_summary: Optional[StampedRecord] = None


class QueuedSosPacket(BaseModel):
    client_incident_id: str
    user_id: str
    device_id: str
    created_at_client: datetime
    lat: float
    lng: float
    accuracy_m: Optional[float] = None
    source_of_location: Literal["gps", "network", "last_known"]
    beach_id: Optional[str] = None
    activity_type: Optional[str] = None
    incident_type: str
    severity: str
    media_refs: list[str] = []
    battery_pct: Optional[int] = None
    signal_strength: Optional[str] = None
    offline_flag: Literal[True] = True


class OfflineSosSyncRequest(BaseModel):
    device_id: str
    packets: list[QueuedSosPacket]


class OfflineSosSyncResult(BaseModel):
    client_incident_id: str
    status: Literal["accepted", "duplicate", "rejected"]
    server_incident_id: Optional[str] = None
    reason: Optional[str] = None


class OfflineSosSyncResponse(BaseModel):
    results: list[OfflineSosSyncResult]
