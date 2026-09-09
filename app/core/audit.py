"""
app/core/audit.py

Canonical audit logger (B4). This is THE single audit write path — every other call site
across the codebase must point here instead of its own local variant. Three variants existed
before this file:
    1. app.core.audit.log_audit_event(...)          <- this one, now canonical
    2. app.audit.record_event(...)                   <- dispatch_state_machine.py, fix import (see below)
    3. app.services.audit_service.log_audit_event(...) <- module18's async version, superseded

Signature matches every real call site found in m814 (sos_service.py, fanout_service.py,
hospital_router_service.py, authority_router_service.py) and modules-20-to-26 (internal_service.py,
incident_service.py, trip_service.py):

    log_audit_event(db, event_type="sos.triggered", entity_type="incident_report",
                     entity_id=incident_id, actor_type="user", actor_id=user_id,
                     payload={...})

Writes to the `audit_events` table, which module18's audit_service.py confirms already exists
(created by Module 2's migration — insert-only table: event_type, entity_type, entity_id,
actor_type, actor_id, payload jsonb, created_at).

Sync version (per project-wide sync decision) — db is a plain SQLAlchemy Session, no await.
"""
import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def log_audit_event(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    actor_type: str = "system",
    actor_id: Optional[Any] = None,
    payload: Optional[dict] = None,
) -> None:
    db.execute(
        text(
            """INSERT INTO audit_events (event_type, entity_type, entity_id, actor_type, actor_id, payload)
               VALUES (:event_type, :entity_type, :entity_id, :actor_type, :actor_id, :payload)"""
        ),
        {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "actor_type": actor_type,
            "actor_id": str(actor_id) if actor_id is not None else None,
            "payload": json.dumps(payload or {}, default=str),
        },
    )
    # Intentionally no db.commit() here — callers already commit as part of their own
    # transaction (confirmed pattern in trip_service.py: log_audit_event(...) is followed
    # by a single db.commit() that covers both the business write and this audit write
    # atomically). Calling commit() here would break that atomicity.