"""Module 0 — constants generated from SCOPE_FREEZE.md. Import these
everywhere instead of hardcoding strings (e.g. sos/schemas.py's IncidentType
enum should derive from INCIDENT_TYPES, not redefine it separately)."""
from __future__ import annotations

USER_JOURNEYS = [
    "pre_check", "trip_check", "sudden_danger", "sos", "rescue", "post_incident_review",
]

INCIDENT_TYPES = [
    "drowning", "injury", "panic", "harassment", "cyclone_storm_surge", "missing_person",
]

ACTIVITY_TYPES = [
    "swimming", "surfing", "boating", "beach_walk", "family_outing",
]

RESPONSE_ROLES = [
    "112", "local_police", "marine_police", "lifeguard", "coast_guard",
    "ambulance", "hospital", "district_disaster_authority",
]

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

# Incident types that require immediate consent override for location/contact sharing,
# regardless of the user's stored consent flags (SOS-only, does not persist).
CONSENT_OVERRIDE_INCIDENT_TYPES = set(INCIDENT_TYPES)


def validate_incident_type(value: str) -> str:
    if value not in INCIDENT_TYPES:
        raise ValueError(f"invalid incident_type '{value}', must be one of {INCIDENT_TYPES}")
    return value


def validate_activity_type(value: str) -> str:
    if value not in ACTIVITY_TYPES:
        raise ValueError(f"invalid activity_type '{value}', must be one of {ACTIVITY_TYPES}")
    return value
