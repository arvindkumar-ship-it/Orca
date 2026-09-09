"""ORCA — GENERALIZE of normalization/canonical_schema.py.
Changes: ALL_ACTIVITY_TYPES swimming/surfing/boating/beach_walk/family_outing
-> fishing/navigation/diving. HARD_OVERRIDE_ALERT_TYPES gains
CYCLONE_WARNING (was already a defined CanonicalAlertType member but never
added to the override set — same fix applied to risk_engine/scoring.py's
mirror list, R7 requires cyclone alerts hard-override). CanonicalForecastEvent
beach_id -> zone_id, source default 'incois' kept (still true for the
ocean_forecast path this canonical shape serves).

PFZ_ADVISORY/SST_RASTER/CHLOROPHYLL_RASTER records deliberately do NOT get a
canonical shape here — ingestion/orca_persistence.py persists them directly
to pfz_advisories/raster_products, bypassing normalization entirely, because
those tables' fields (bearing_deg, tile footprints, raster_url) don't map
onto either CanonicalHazardEvent or CanonicalForecastEvent's shape without
distorting one or the other. This is a deliberate two-path design, not an
oversight — stated plainly rather than silently forcing a bad-fit schema."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CanonicalAlertType(str, Enum):
    TSUNAMI_WARNING = "tsunami_warning"
    STORM_SURGE_WARNING = "storm_surge_warning"
    CYCLONE_WARNING = "cyclone_warning"
    HIGH_WAVE_WARNING = "high_wave_warning"
    EVACUATION_ORDER = "evacuation_order"
    BEACH_CLOSURE = "beach_closure"
    COAST_GUARD_CLOSURE = "coast_guard_closure"
    OTHER = "other"


HARD_OVERRIDE_ALERT_TYPES = {
    CanonicalAlertType.TSUNAMI_WARNING,
    CanonicalAlertType.STORM_SURGE_WARNING,
    CanonicalAlertType.EVACUATION_ORDER,
    CanonicalAlertType.BEACH_CLOSURE,
    CanonicalAlertType.COAST_GUARD_CLOSURE,
    CanonicalAlertType.CYCLONE_WARNING,  # NEW — R7
}

EVACUATION_ALERT_TYPES = {
    CanonicalAlertType.EVACUATION_ORDER,
    CanonicalAlertType.TSUNAMI_WARNING,
}

ALL_ACTIVITY_TYPES = {"fishing", "navigation", "diving"}


class CanonicalHazardEvent(BaseModel):
    source_system: str
    source_alert_id: str
    alert_type: CanonicalAlertType
    severity: str
    title: Optional[str] = None
    description: Optional[str] = None
    geometry: Optional[dict[str, Any]] = None
    issued_at: datetime
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    eta_minutes: Optional[int] = None
    hard_override_flag: bool = False
    evacuation_flag: bool = False
    affected_activity_types: list[str] = Field(default_factory=lambda: sorted(ALL_ACTIVITY_TYPES))
    confidence: float = 1.0
    uncertainty_flags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class CanonicalForecastEvent(BaseModel):
    zone_id: Optional[str] = None  # was beach_id — resolved by nearest-zone matching before persistence
    station_source_id: str
    forecast_time: datetime
    wave_height: Optional[float] = None
    current_speed: Optional[float] = None
    wind_speed: Optional[float] = None
    swell_height: Optional[float] = None
    tide_state: Optional[str] = None
    rainfall: Optional[float] = None
    visibility: Optional[float] = None
    water_quality: Optional[float] = None
    source: str = "incois"
    confidence: float = 1.0
    uncertainty_flags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
