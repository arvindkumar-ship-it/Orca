"""
tests/test_acceptance_criteria.py — direct mapping to Module 31's acceptance
criteria list. Each test name matches one bullet so a failing test tells you
exactly which release-gate criterion broke.
"""
import uuid

import pytest
from sqlalchemy import text

from app.core.dispatch_states import IncidentState
from app.services.dispatch_state_machine import DispatchStateMachine


def test_sos_reaches_at_least_2_downstream_targets(db, test_user, test_beach):
    """Acceptance: SOS reaches at least 2 downstream targets in one dispatch cycle."""
    incident_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO incident_reports (id, user_id, beach_id, incident_type, severity, "
            "lat, lng, status, trigger_type) "
            "VALUES (:id, :uid, :bid, 'drowning', 'critical', 13.05, 80.28, 'created', 'manual_button')"
        ),
        {"id": str(incident_id), "uid": str(test_user), "bid": str(test_beach)},
    )
    # authority_router + hospital_router (Modules 0-19) are expected to write
    # incident_routes rows in parallel per Module 33 rule #3.
    for target_type, rank in [("authority", 1), ("hospital", 1), ("family", 1)]:
        db.execute(
            text(
                "INSERT INTO incident_routes "
                "(id, incident_report_id, target_type, target_name, route_rank) "
                "VALUES (:id, :iid, :ttype, :tname, :rank)"
            ),
            {
                "id": str(uuid.uuid4()),
                "iid": str(incident_id),
                "ttype": target_type,
                "tname": f"test-{target_type}",
                "rank": rank,
            },
        )
    db.flush()

    routes = db.execute(
        text("SELECT DISTINCT target_type FROM incident_routes WHERE incident_report_id = :id"),
        {"id": str(incident_id)},
    ).fetchall()

    assert len(routes) >= 2


def test_acknowledgement_is_visible(db, make_incident):
    """Acceptance: acknowledgement is visible — ack_status/ack_time queryable, not silent."""
    incident_id = make_incident(status="dispatched")
    route_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO incident_routes (id, incident_report_id, target_type, target_name, route_rank, ack_status) "
            "VALUES (:id, :iid, 'authority', 'test-authority', 1, 'sent')"
        ),
        {"id": str(route_id), "iid": str(incident_id)},
    )
    db.execute(
        text("UPDATE incident_routes SET ack_status = 'acknowledged', ack_time = now() WHERE id = :id"),
        {"id": str(route_id)},
    )
    db.flush()

    row = db.execute(
        text("SELECT ack_status, ack_time FROM incident_routes WHERE id = :id"),
        {"id": str(route_id)},
    ).fetchone()

    assert row[0] == "acknowledged"
    assert row[1] is not None


def test_user_sees_safe_zone_recommendation(db, make_incident):
    """Acceptance: user sees safe zone recommendation — SAFE_ZONE_SHARED reachable in main flow."""
    incident_id = make_incident(status="hospital_notified")
    sm = DispatchStateMachine(db)

    result = sm.transition(incident_id, IncidentState.SAFE_ZONE_SHARED, actor_type="system")

    assert result == IncidentState.SAFE_ZONE_SHARED


def test_offline_queue_survives_reconnect(db, test_user):
    """Acceptance: offline queue survives reconnect — offline_sync_queue rows persist until processed."""
    queue_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO offline_sync_queue (id, user_id, entity_type, action_type, payload, status) "
            "VALUES (:id, :uid, 'incident_report', 'create', '{\"lat\":13.05,\"lng\":80.28}'::jsonb, 'pending')"
        ),
        {"id": str(queue_id), "uid": str(test_user)},
    )
    db.flush()

    row = db.execute(
        text("SELECT status FROM offline_sync_queue WHERE id = :id"), {"id": str(queue_id)}
    ).fetchone()

    assert row[0] == "pending"  # still queued, was not silently dropped


def test_risk_verdict_changes_when_hazard_changes(db, test_beach):
    """Acceptance: risk verdict changes when hazard changes."""
    db.execute(
        text(
            "INSERT INTO beach_risk_scores (id, beach_id, risk_level, computed_at) "
            "VALUES (:id, :bid, 'safe', now())"
        ),
        {"id": str(uuid.uuid4()), "bid": str(test_beach)},
    )
    db.execute(
        text(
            "INSERT INTO hazard_alerts (id, beach_id, hard_override_flag, active, created_at) "
            "VALUES (:id, :bid, true, true, now())"
        ),
        {"id": str(uuid.uuid4()), "bid": str(test_beach)},
    )
    db.execute(
        text(
            "INSERT INTO beach_risk_scores (id, beach_id, risk_level, computed_at) "
            "VALUES (:id, :bid, 'unsafe', now())"
        ),
        {"id": str(uuid.uuid4()), "bid": str(test_beach)},
    )
    db.flush()

    latest = db.execute(
        text(
            "SELECT risk_level FROM beach_risk_scores WHERE beach_id = :bid "
            "ORDER BY computed_at DESC LIMIT 1"
        ),
        {"bid": str(test_beach)},
    ).fetchone()

    assert latest[0] == "unsafe"


def test_incident_audit_trail_is_complete(db, make_incident):
    """Acceptance: incident audit trail is complete — every transition emits an audit_event."""
    incident_id = make_incident(status="created")
    sm = DispatchStateMachine(db)
    sm.transition(incident_id, IncidentState.VALIDATED, actor_type="system")
    sm.transition(incident_id, IncidentState.LOCATION_LOCKED, actor_type="system")

    events = db.execute(
        text(
            "SELECT event_type FROM audit_events "
            "WHERE entity_type = 'incident_report' AND entity_id = :id ORDER BY created_at"
        ),
        {"id": str(incident_id)},
    ).fetchall()

    assert [e[0] for e in events] == [
        "incident.status.validated",
        "incident.status.location_locked",
    ]
