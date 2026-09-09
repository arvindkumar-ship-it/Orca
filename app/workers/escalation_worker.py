"""
Module 26 — escalation_worker, now wired to Module 27's DispatchStateMachine.
Celery Beat calls check_ack_timeouts() every N seconds (see beat schedule below).
Each due timer = one forced transition (dispatched->timeout->escalated->fallback_112).
Module 33 rule: never rely on one responder only — each escalation step re-fans-out
via DispatchStateMachine._on_enter's notification hook, it does not just log.
"""
from __future__ import annotations

import logging
import uuid

from celery import shared_task

from app.core.db import SessionLocal
from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.escalation_service import get_due_timers, consume_timer

logger = logging.getLogger(__name__)


@shared_task(name="workers.escalation.check_ack_timeouts")
def check_ack_timeouts() -> dict:
    db = SessionLocal()
    processed, failed = 0, 0
    try:
        due = get_due_timers(db, limit=200)
        for timer in due:
            incident_id: uuid.UUID = timer["incident_id"]
            target_state = IncidentState(timer["on_timeout_state"])
            try:
                sm = DispatchStateMachine(db)
                current = sm.get_current_state(incident_id)
                # Only fire if still in the state the timer was set for —
                # avoids double-escalating an incident someone already
                # acknowledged/closed manually (Module 33: ops override respected).
                if current in (IncidentState.DISPATCHED, IncidentState.TIMEOUT, IncidentState.ESCALATED):
                    sm.transition(
                        incident_id,
                        target_state,
                        actor_type="system",
                        reason="ack_timeout",
                    )
                consume_timer(db, timer_id=timer["timer_id"])
                db.commit()
                processed += 1
            except InvalidTransitionError as e:
                logger.warning("escalation skip incident=%s: %s", incident_id, e)
                consume_timer(db, timer_id=timer["timer_id"])
                db.commit()
                failed += 1
            except Exception:
                db.rollback()
                logger.exception("escalation failed incident=%s", incident_id)
                failed += 1
    finally:
        db.close()
    return {"processed": processed, "failed": failed}
