"""app/models/__init__.py — MERGED for the ORCA overlay.

Aggregates BOTH:
  - WaveSafe originals, kept alive via the `_wavesafe` suffix copies
    (Beach, SafeZone from geospatial_wavesafe.py; BeachActivityProfile/
    BeachForecast/HazardAlert/BeachRiskScore/TripPlan/TripRiskSnapshot from
    forecast_risk_wavesafe.py) — still imported by ingestion/persistence.py,
    forecast_engine/*, trip_planner/* (all COPY, unrouted in app/main.py
    but left functionally intact rather than deleted, per "reuse before
    rewrite" — nothing breaks anything else by staying importable).
  - ORCA's new/generalized tables (MarineZone, SafeHarbor,
    MaritimeBoundary, MpaZone, ZoneActivityProfile, ZoneForecast,
    ZoneRiskScore, PfzAdvisory, RasterProduct, VoyageWatch).

Jurisdiction/Hospital/RescuePost are unchanged (COPY) and now live under
geospatial_wavesafe.py alongside Beach/SafeZone, since ORCA's own
geospatial.py deliberately doesn't redefine them (see that file's header).
"""
from .base import Base
from .core import User, UserDevice, EmergencyContact

from .geospatial_wavesafe import Beach, SafeZone, Jurisdiction, Hospital, RescuePost
from .geospatial import MarineZone, SafeHarbor, MaritimeBoundary, MpaZone

from .forecast_risk_wavesafe import (
    BeachActivityProfile, BeachForecast, HazardAlert, BeachRiskScore,
    TripStatus, TripRecommendation, TripPlan, TripRiskSnapshot,
)
from .forecast_risk import ZoneActivityProfile, ZoneForecast, ZoneRiskScore

from .ocean_products import PfzAdvisory, RasterProduct
from .voyage_watch import VoyageWatch

from .incident import (
    IncidentReport, IncidentRoute, IncidentStatusHistory, NotificationQueue,
    AuditEvent, UserContact, OfflineSyncQueue,
)
from .otp import OTPCode
from .tracking import LiveTrackingSession, LocationPing
from .safezone import SafeZoneGuidance
from .emergency_share import EmergencyShareSession, EmergencyShareTarget

__all__ = [
    "Base",
    "User", "UserDevice", "EmergencyContact",
    "Beach", "SafeZone", "Jurisdiction", "Hospital", "RescuePost",
    "MarineZone", "SafeHarbor", "MaritimeBoundary", "MpaZone",
    "BeachActivityProfile", "BeachForecast", "HazardAlert", "BeachRiskScore",
    "TripStatus", "TripRecommendation", "TripPlan", "TripRiskSnapshot",
    "ZoneActivityProfile", "ZoneForecast", "ZoneRiskScore",
    "PfzAdvisory", "RasterProduct", "VoyageWatch",
    "IncidentReport", "IncidentStatusHistory", "IncidentRoute", "NotificationQueue",
    "AuditEvent", "UserContact", "OfflineSyncQueue",
    "OTPCode",
    "LiveTrackingSession", "LocationPing",
    "SafeZoneGuidance",
    "EmergencyShareSession", "EmergencyShareTarget",
]
