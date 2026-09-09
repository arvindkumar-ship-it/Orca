"""
tests/test_dispatch_state_machine.py — Module 31 unit tests for Module 27.
Covers: "wrong jurisdiction routing" indirectly (invalid transitions), and
the explicit acceptance-adjacent rule "never store incident without status history".
"""
import pytest

from app.core.dispatch_states import IncidentState, InvalidTransitionError
from app.services.dispatch_state_machine import DispatchStateMachine


def test_valid_happy_path_transition(db, make_incident):
    incident_id = make_incident(status="created")
    sm = DispatchStateMachine(db)

    result = sm.transition(incident_id, IncidentState.VALIDATED, actor_type="system")

    assert result == IncidentState.VALIDATED
    assert sm.get_current_state(incident_id) == IncidentState.VALIDATED


def test_skipping_a_state_is_rejected(db, make_incident):
    incident_id = make_incident(status="created")
    sm = DispatchStateMachine(db)

    with pytest.raises(InvalidTransitionError):
        sm.transition(incident_id, IncidentState.DISPATCHED, actor_type="system")


def test_closed_is_terminal(db, make_incident):
    incident_id = make_incident(status="closed")
    sm = DispatchStateMachine(db)

    with pytest.raises(InvalidTransitionError):
        sm.transition(incident_id, IncidentState.RESOLVED, actor_type="system")


def test_dispatched_can_branch_to_timeout(db, make_incident):
    incident_id = make_incident(status="dispatched")
    sm = DispatchStateMachine(db)

    result = sm.transition(incident_id, IncidentState.TIMEOUT, actor_type="system", reason="ack_timeout")

    assert result == IncidentState.TIMEOUT


def test_every_transition_writes_status_history(db, make_incident):
    """Module 33 rule: never store incident without status history."""
    incident_id = make_incident(status="created")
    sm = DispatchStateMachine(db)
    sm.transition(incident_id, IncidentState.VALIDATED, actor_type="system")

    from sqlalchemy import text

    row = db.execute(
        text(
            "SELECT from_status, to_status FROM incident_status_history "
            "WHERE incident_report_id = :id ORDER BY changed_at DESC LIMIT 1"
        ),
        {"id": str(incident_id)},
    ).fetchone()

    assert row is not None
    assert row[0] == "created"
    assert row[1] == "validated"


def test_manual_ops_can_force_close(db, make_incident):
    incident_id = make_incident(status="manual_ops")
    sm = DispatchStateMachine(db)

    result = sm.transition(incident_id, IncidentState.CLOSED, actor_type="operator", reason="ops override")

    assert result == IncidentState.CLOSED
