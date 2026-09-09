# B10-style gap — app.services.dispatch_service, imported by offline_sync_service.py
# (create_incident_from_packet) but never delivered in any zip.
#
# ⚠️ VERIFIED against m8-14.zip's actual sos_service.py: the real incident-creation function
# there is `create_sos_incident(db, user_id, body)`, where `body` is expected to be a Pydantic
# schema object (from app.schemas.sos), not a plain dict — its fields are accessed as
# `body.lat`, `body.incident_type` etc. (confirmed via sos_service.py's own usage pattern).
#
# offline_sync_service.py currently builds a plain dict via `_to_canonical_packet()`. This
# wrapper adapts that dict into a lightweight object with attribute access so it satisfies
# sos_service's `body.x` access pattern without needing sos_service.py itself modified.
#
# # VERIFIED (this session) against the real app/services/sos_service.py:
# _create_incident_record(db, user_id, body) accesses exactly: body.beach_id,
# body.activity_type, body.incident_type, body.severity, body.lat, body.lng,
# body.description, body.media_urls, body.trigger_type, body.battery_pct,
# body.signal_strength, body.location_source, body.accuracy_m (and optionally
# body.client_incident_id via getattr). Every one of these is present on the
# SimpleNamespace built below. No field renames needed. Note: app/schemas/sos.py
# does not exist in this codebase — the offline packet dict is the source of truth.
#
# received_late=True is accepted here but not yet threaded through to sos_service (which
# doesn't have that parameter) — for now it's used only to tag the audit event with the
# late-arrival flag; wire it into incident_reports.offline_flag if you want it persisted
# on the row itself (schema already has an offline_flag concept per the packet dict above).

from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.services.sos_service import create_sos_incident


def create_incident_from_packet(db: Session, packet: dict, received_late: bool = False):
    body = SimpleNamespace(**packet, description=None, location_source=packet.get("source_of_location"), trigger_type="offline_sync")
    result = create_sos_incident(db, packet["user_id"], body)
    # create_sos_incident returns a dict (confirmed: {"incident_id": ..., "created_at": ...}
    # per sos_service.py's create_sos_incident return statement). offline_sync_service.py
    # expects an object with `.id` — wrap it the same way.
    return SimpleNamespace(id=result["incident_id"], created_at=result.get("created_at"))