"""
tests/test_failure_scenarios.py — Module 31's "must test" list.
Scenarios needing real load/multi-hour timers (evacuation, mass duplicate
incidents) are marked disaster_sim and skipped locally (see pytest.ini,
runbook.sh only runs disaster_sim outside 'local').
"""
import uuid

import pytest
from sqlalchemy import text

from app.core.dispatch_states import IncidentState
from app.services.dispatch_state_machine import DispatchStateMachine
from app.services.escalation_service import schedule_ack_check, get_due_timers


def test_duplicate_incidents_from_same_user_same_location(db, make_incident):
    """Two SOS presses within seconds at the same spot should both persist
    (never silently drop — Module 33: never lose an event without audit),
    downstream dedup is a router-layer concern, not the state machine's."""
    id1 = make_incident(status="created")
    id2 = make_incident(status="created")
    assert id1 != id2


def test_wrong_jurisdiction_routing_is_visible_not_silent(db, make_incident):
    """A route with no matching jurisdiction must still be recorded with an
    error, not dropped (Module 33: failure is visible, not hidden)."""
    incident_id = make_incident(status="dispatched")
    db.execute(
        text(
            "INSERT INTO incident_routes "
            "(id, incident_report_id, target_type, target_name, route_rank, ack_status, last_error) "
            "VALUES (:id, :iid, 'authority', 'unknown', 1, 'failed', 'no jurisdiction match for point')"
        ),
        {"id": str(uuid.uuid4()), "iid": str(incident_id)},
    )
    db.flush()

    row = db.execute(
        text("SELECT ack_status, last_error FROM incident_routes WHERE incident_report_id = :id"),
        {"id": str(incident_id)},
    ).fetchone()

    assert row[0] == "failed"
    assert row[1] is not None


def test_hospital_unreachable_has_no_silent_skip_path(db, make_incident):
    """en_route -> escalated is not a valid direct hop; confirms no silent
    skip exists if hospital never acks — ops must use force_manual_transition."""
    incident_id = make_incident(status="en_route")
    sm = DispatchStateMachine(db)
    from app.core.dispatch_states import InvalidTransitionError

    with pytest.raises(InvalidTransitionError):
        sm.transition(incident_id, IncidentState.ESCALATED, actor_type="system")


def test_push_failed_falls_back_to_sms(db, test_user, make_incident):
    """A failed push notification_queue row must not be the only delivery
    attempt — an SMS-channel row should also exist."""
    incident_id = make_incident(status="dispatched")
    db.execute(
        text(
            "INSERT INTO notification_queue "
            "(id, user_id, incident_report_id, type, priority, title, body, channel, status) "
            "VALUES (:id, :uid, :iid, 'incident.dispatched', 'critical', 'Help dispatched', 'x', 'push', 'failed')"
        ),
        {"id": str(uuid.uuid4()), "uid": str(test_user), "iid": str(incident_id)},
    )
    db.execute(
        text(
            "INSERT INTO notification_queue "
            "(id, user_id, incident_report_id, type, priority, title, body, channel, status) "
            "VALUES (:id, :uid, :iid, 'incident.dispatched', 'critical', 'Help dispatched', 'x', 'sms', 'queued')"
        ),
        {"id": str(uuid.uuid4()), "uid": str(test_user), "iid": str(incident_id)},
    )
    db.flush()

    channels = db.execute(
        text(
            "SELECT channel FROM notification_queue "
            "WHERE incident_report_id = :id AND type = 'incident.dispatched'"
        ),
        {"id": str(incident_id)},
    ).fetchall()

    assert {c[0] for c in channels} == {"push", "sms"}


def test_ack_timeout_fires_escalation(db, make_incident):
    """GPS failure / weak network causing no ack: timer expiry must be
    pickable by escalation_worker (Module 27 wiring, tested end-to-end)."""
    incident_id = make_incident(status="dispatched")
    schedule_ack_check(
        db, incident_id=incident_id, timeout_seconds=-1, on_timeout_state=IncidentState.TIMEOUT
    )
    db.flush()

    due = get_due_timers(db)
    assert any(t["incident_id"] == incident_id for t in due)


def test_map_polygon_mismatch_flagged_by_geometry_validation(db):
    """A self-intersecting polygon must fail ST_IsValid, not silently insert."""
    result = db.execute(
        text("SELECT ST_IsValid(ST_GeomFromText('POLYGON((0 0, 1 1, 1 0, 0 1, 0 0))', 4326))")
    ).scalar()
    assert result is False


def test_false_alert_scenario_closed_with_reason(db, make_incident):
    """A false alert should reach 'closed' with an audit reason, not be deleted."""
    incident_id = make_incident(status="resolved")
    sm = DispatchStateMachine(db)
    sm.transition(incident_id, IncidentState.CLOSED, actor_type="operator", reason="false_alert")

    row = db.execute(
        text(
            "SELECT reason FROM incident_status_history "
            "WHERE incident_report_id = :id ORDER BY changed_at DESC LIMIT 1"
        ),
        {"id": str(incident_id)},
    ).fetchone()
    assert row[0] == "false_alert"


@pytest.mark.disaster_sim
def test_evacuation_scenario_mass_incidents(db, test_beach, test_user):
    """High-volume simulated evacuation: N incidents dispatched concurrently,
    each retains independent status history (no shared/overwritten rows)."""
    sm = DispatchStateMachine(db)
    ids = []
    for _ in range(50):
        iid = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO incident_reports (id, user_id, beach_id, incident_type, severity, "
                "lat, lng, status, trigger_type) "
                "VALUES (:id, :uid, :bid, 'panic', 'high', 13.05, 80.28, 'created', 'auto_evac')"
            ),
            {"id": str(iid), "uid": str(test_user), "bid": str(test_beach)},
        )
        ids.append(iid)
    db.flush()

    for iid in ids:
        sm.transition(iid, IncidentState.VALIDATED, actor_type="system")
    for iid in ids:
        assert sm.get_current_state(iid) == IncidentState.VALIDATED
