# Product Scope Freeze — Coastal Tourism Safety Platform

## User journeys (frozen, 6)
1. Pre-check — user checks a beach's safety verdict before choosing it.
2. Trip check — system monitors conditions during a planned trip window, alerts on change.
3. Sudden danger — real-time hazard appears while user is at/near the beach.
4. SOS — user or system triggers an emergency dispatch.
5. Rescue — authorities/hospital coordinate response until closure.
6. Post-incident review — feedback, audit trail, closure record.

## Incident types (frozen, 6)
drowning, injury, panic, harassment, cyclone_storm_surge, missing_person

## Activity types (frozen, 5)
swimming, surfing, boating, beach_walk, family_outing

## Response roles (frozen, 8)
112, local_police, marine_police, lifeguard, coast_guard, ambulance, hospital, district_disaster_authority

## Privacy boundaries
- Location sharing requires explicit consent (`users.consent_location`).
- Emergency contact sharing requires explicit consent (`users.consent_emergency_share`).
- During an active SOS, consent is treated as already granted for that incident only —
  it does not change the stored consent flags.
- Audit retention: `audit_events` and `incident_status_history` are retained indefinitely;
  no auto-delete job — deletions must be a deliberate compliance action, not a default.
- Data minimization: raw payloads (`raw_payload` columns) are stored for replay/audit only,
  never surfaced directly to end users.

## Non-negotiable principle
The system must not be a notification wrapper. It must do four real things:
convert raw official data into beach decisions, detect trip-risk changes,
dispatch real emergencies with exact location, coordinate rescue through
authorities and hospitals.

---
This document is the single source of truth for the enums below. If this file
changes, `app/constants.py` and every module that hardcodes these values
(`sos/schemas.py`'s `IncidentType`, `beach_activity_profiles.activity_type`,
`jurisdictions.authority_type`) must be updated together — do not let them drift.
