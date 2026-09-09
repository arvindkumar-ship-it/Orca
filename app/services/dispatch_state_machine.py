"""
Module 27 — Dispatch State Machine service.
Single authoritative place that mutates incident_reports.status.
Every transition: (1) validates against TRANSITIONS graph, (2) writes
incident_status_history, (3) writes audit_events, (4) fires the matching
DispatchEvent for notification/escalation hooks, (5) commits atomically.

Depends on (per project convention — provided by earlier modules):
- core.db.get_db / SessionLocal
- audit.record_event(db, event_type, entity_type, entity_id, actor_type, actor_id, payload)
- notification_service.enqueue(...)   (Module 23/26)
- escalation_service.schedule_ack_check(...) (Module 26 escalation_worker)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dispatch_states import (
    ACK_TIMEOUT_STATES,
    ACK_TIMEOUT_SECONDS,
    ESCALATION_TIMEOUT_SECONDS,
    FALLBACK_TIMEOUT_SECONDS,
    DispatchEvent,
    IncidentState,
    InvalidTransitionError,
    is_terminal,
    is_valid_transition,
)
from app.core.audit import log_audit_event
from app.services.notification_service import enqueue as notify_enqueue
from app.services.escalation_service import schedule_ack_check, cancel_ack_check

# state -> event fired on successful entry (used for notification fanout / audit payload)
_STATE_EVENT_MAP: dict[IncidentState, DispatchEvent] = {
    IncidentState.CREATED: DispatchEvent.INCIDENT_CREATED,
    IncidentState.LOCATION_LOCKED: DispatchEvent.LOCATION_LOCKED,
    IncidentState.PACKED: DispatchEvent.PACKET_BUILT,
    IncidentState.DISPATCHED: DispatchEvent.DISPATCHED,
    IncidentState.ACKNOWLEDGED: DispatchEvent.AUTHORITY_ACK,
    IncidentState.HOSPITAL_NOTIFIED: DispatchEvent.HOSPITAL_ACK,
    IncidentState.SAFE_ZONE_SHARED: DispatchEvent.SAFEZONE_SHARED,
    IncidentState.TIMEOUT: DispatchEvent.ESCALATION_TIMEOUT,
    IncidentState.CLOSED: DispatchEvent.INCIDENT_CLOSED,
}


class DispatchStateMachine:
    """Bound to one DB session; one call = one transition = one transaction."""

    def __init__(self, db: Session):
        self.db = db

    def get_current_state(self, incident_id: uuid.UUID) -> IncidentState:
        row = self.db.execute(
            text("SELECT status FROM incident_reports WHERE id = :id"),
            {"id": str(incident_id)},
        ).fetchone()
        if row is None:
            raise ValueError(f"incident_report {incident_id} not found")
        return IncidentState(row[0])

    def transition(
        self,
        incident_id: uuid.UUID,
        to_state: IncidentState,
        *,
        actor_type: str,
        actor_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        extra_payload: Optional[dict] = None,
    ) -> IncidentState:
        """
        Validate + apply a single transition. Raises InvalidTransitionError
        on illegal moves. Caller commits (or this runs inside caller's
        transaction) — we do NOT commit here so multi-step calls (e.g.
        dispatch -> schedule ack timer) stay atomic with the caller.
        """
        current = self.get_current_state(incident_id)

        if not is_valid_transition(current, to_state):
            raise InvalidTransitionError(current, to_state)

        now = datetime.now(timezone.utc)

        self.db.execute(
            text(
                "UPDATE incident_reports SET status = :status, updated_at = :now "
                "WHERE id = :id"
            ),
            {"status": to_state.value, "now": now, "id": str(incident_id)},
        )

        self.db.execute(
            text(
                "INSERT INTO incident_status_history "
                "(id, incident_report_id, from_status, to_status, reason, changed_at) "
                "VALUES (:hid, :iid, :from_s, :to_s, :reason, :now)"
            ),
            {
                "hid": str(uuid.uuid4()),
                "iid": str(incident_id),
                "from_s": current.value,
                "to_s": to_state.value,
                "reason": reason,
                "now": now,
            },
        )

        log_audit_event(
            self.db,
            event_type=f"incident.status.{to_state.value}",
            entity_type="incident_report",
            entity_id=incident_id,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "from_status": current.value,
                "to_status": to_state.value,
                "reason": reason,
                **(extra_payload or {}),
            },
        )

        self._on_enter(incident_id, to_state, actor_type, actor_id)

        return to_state

    def _on_enter(
        self,
        incident_id: uuid.UUID,
        state: IncidentState,
        actor_type: str,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Side effects triggered purely by entering a state — never silent."""

        # 1. ack-timeout states start (or restart) an escalation timer
        if state in ACK_TIMEOUT_STATES:
            schedule_ack_check(
                self.db,
                incident_id=incident_id,
                timeout_seconds=ACK_TIMEOUT_SECONDS,
                on_timeout_state=IncidentState.TIMEOUT,
            )
        elif state == IncidentState.TIMEOUT:
            # timeout itself escalates on its own clock (Module 26 escalation_worker polls this)
            schedule_ack_check(
                self.db,
                incident_id=incident_id,
                timeout_seconds=ESCALATION_TIMEOUT_SECONDS,
                on_timeout_state=IncidentState.ESCALATED,
            )
        elif state == IncidentState.ESCALATED:
            schedule_ack_check(
                self.db,
                incident_id=incident_id,
                timeout_seconds=FALLBACK_TIMEOUT_SECONDS,
                on_timeout_state=IncidentState.FALLBACK_112,
            )
        else:
            # any non-ack state cancels a pending ack timer for this incident
            cancel_ack_check(self.db, incident_id=incident_id)

        # 2. terminal state cleanup
        if is_terminal(state):
            cancel_ack_check(self.db, incident_id=incident_id)

        # 3. notification fanout — Rule (Module 33): critical alert never low priority
        event = _STATE_EVENT_MAP.get(state)
        if event is not None:
            priority = "critical" if state in (
                IncidentState.DISPATCHED,
                IncidentState.TIMEOUT,
                IncidentState.ESCALATED,
                IncidentState.FALLBACK_112,
            ) else "high"
            notify_enqueue(
                self.db,
                incident_report_id=incident_id,
                type=event.value,
                priority=priority,
                title=_notification_title(state),
                body=_notification_body(state),
            )


def _notification_title(state: IncidentState) -> str:
    return {
        IncidentState.CREATED: "Incident reported",
        IncidentState.LOCATION_LOCKED: "Location confirmed",
        IncidentState.PACKED: "Incident packet ready",
        IncidentState.DISPATCHED: "Emergency dispatched",
        IncidentState.ACKNOWLEDGED: "Responder acknowledged",
        IncidentState.HOSPITAL_NOTIFIED: "Hospital notified",
        IncidentState.SAFE_ZONE_SHARED: "Safe zone route shared",
        IncidentState.TIMEOUT: "No acknowledgement received",
        IncidentState.ESCALATED: "Incident escalated",
        IncidentState.FALLBACK_112: "Falling back to 112",
        IncidentState.CLOSED: "Incident closed",
    }.get(state, state.value.replace("_", " ").title())


def _notification_body(state: IncidentState) -> str:
    return {
        IncidentState.DISPATCHED: "Authorities and hospital have been notified of your emergency.",
        IncidentState.TIMEOUT: "Primary responder did not acknowledge in time. Escalating.",
        IncidentState.ESCALATED: "Escalating to higher jurisdiction level.",
        IncidentState.FALLBACK_112: "Routing directly to 112 emergency services.",
        IncidentState.CLOSED: "This incident has been marked closed.",
    }.get(state, "")


def force_manual_transition(
    db: Session,
    incident_id: uuid.UUID,
    to_state: IncidentState,
    *,
    operator_id: uuid.UUID,
    reason: str,
) -> IncidentState:
    """
    Module 33 rule: manual override only for operators. Same graph, same
    audit trail — just a distinct actor_type so it's queryable separately.
    """
    sm = DispatchStateMachine(db)
    result = sm.transition(
        incident_id,
        to_state,
        actor_type="operator",
        actor_id=operator_id,
        reason=reason,
        extra_payload={"manual_override": True},
    )
    db.commit()
    return result
