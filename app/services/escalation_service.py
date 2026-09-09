"""
Module 26/27 support — ack-timer persistence.
One active timer per incident (enforced by partial unique index on ack_timers).
escalation_worker (Celery Beat) polls due timers and drives the state machine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


def schedule_ack_check(
    db: Session,
    *,
    incident_id: uuid.UUID,
    timeout_seconds: int,
    on_timeout_state,  # IncidentState
) -> None:
    """Replace any existing active timer for this incident with a new one."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
    db.execute(
        text(
            "UPDATE ack_timers SET active = false "
            "WHERE incident_report_id = :iid AND active = true"
        ),
        {"iid": str(incident_id)},
    )
    db.execute(
        text(
            "INSERT INTO ack_timers "
            "(id, incident_report_id, on_timeout_state, expires_at, active, created_at) "
            "VALUES (:id, :iid, :state, :exp, true, :now)"
        ),
        {
            "id": str(uuid.uuid4()),
            "iid": str(incident_id),
            "state": on_timeout_state.value,
            "exp": expires_at,
            "now": datetime.now(timezone.utc),
        },
    )


def cancel_ack_check(db: Session, *, incident_id: uuid.UUID) -> None:
    db.execute(
        text(
            "UPDATE ack_timers SET active = false "
            "WHERE incident_report_id = :iid AND active = true"
        ),
        {"iid": str(incident_id)},
    )


def get_due_timers(db: Session, *, limit: int = 100) -> list[dict]:
    """Fetch expired, still-active timers for escalation_worker to process."""
    rows = db.execute(
        text(
            "SELECT id, incident_report_id, on_timeout_state "
            "FROM ack_timers "
            "WHERE active = true AND expires_at <= :now "
            "ORDER BY expires_at ASC LIMIT :limit"
        ),
        {"now": datetime.now(timezone.utc), "limit": limit},
    ).fetchall()
    return [
        {"timer_id": r[0], "incident_id": r[1], "on_timeout_state": r[2]}
        for r in rows
    ]


def consume_timer(db: Session, *, timer_id: uuid.UUID) -> None:
    """Mark a timer processed so escalation_worker doesn't re-fire it."""
    db.execute(
        text("UPDATE ack_timers SET active = false WHERE id = :id"),
        {"id": str(timer_id)},
    )
