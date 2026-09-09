"""
Module 27 — Dispatch State Machine: canonical states, transition graph, event names.
No other module may hardcode incident status strings — import from here.
"""
from enum import Enum


class IncidentState(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    LOCATION_LOCKED = "location_locked"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    ROUTED = "routed"
    EN_ROUTE = "en_route"
    HOSPITAL_NOTIFIED = "hospital_notified"
    SAFE_ZONE_SHARED = "safe_zone_shared"
    RESOLVED = "resolved"
    CLOSED = "closed"
    # failure branch
    TIMEOUT = "timeout"
    ESCALATED = "escalated"
    FALLBACK_112 = "fallback_112"
    MANUAL_OPS = "manual_ops"


class DispatchEvent(str, Enum):
    SOS_TRIGGERED = "sos.triggered"
    INCIDENT_CREATED = "incident.created"
    LOCATION_LOCKED = "incident.location.locked"
    PACKET_BUILT = "incident.packet.built"
    DISPATCHED = "incident.dispatched"
    AUTHORITY_ACK = "authority.ack.received"
    HOSPITAL_ACK = "hospital.ack.received"
    SAFEZONE_SHARED = "safezone.shared"
    NOTIFICATION_SENT = "notification.sent"
    ESCALATION_TIMEOUT = "escalation.timeout"
    INCIDENT_CLOSED = "incident.closed"


# Main happy-path flow (strict order, no skipping)
MAIN_FLOW = [
    IncidentState.CREATED,
    IncidentState.VALIDATED,
    IncidentState.LOCATION_LOCKED,
    IncidentState.PACKED,
    IncidentState.DISPATCHED,
    IncidentState.ACKNOWLEDGED,
    IncidentState.ROUTED,
    IncidentState.EN_ROUTE,
    IncidentState.HOSPITAL_NOTIFIED,
    IncidentState.SAFE_ZONE_SHARED,
    IncidentState.RESOLVED,
    IncidentState.CLOSED,
]

# Allowed transitions: from_state -> set(to_states)
TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.CREATED: {IncidentState.VALIDATED},
    IncidentState.VALIDATED: {IncidentState.LOCATION_LOCKED},
    IncidentState.LOCATION_LOCKED: {IncidentState.PACKED},
    IncidentState.PACKED: {IncidentState.DISPATCHED},
    IncidentState.DISPATCHED: {
        IncidentState.ACKNOWLEDGED,
        IncidentState.HOSPITAL_NOTIFIED,  # hospital ack can arrive before authority ack (parallel dispatch)
        IncidentState.TIMEOUT,  # ack failure branch
    },
    IncidentState.ACKNOWLEDGED: {IncidentState.ROUTED},
    IncidentState.ROUTED: {IncidentState.EN_ROUTE},
    IncidentState.EN_ROUTE: {IncidentState.HOSPITAL_NOTIFIED},
    IncidentState.HOSPITAL_NOTIFIED: {IncidentState.SAFE_ZONE_SHARED},
    IncidentState.SAFE_ZONE_SHARED: {IncidentState.RESOLVED},
    IncidentState.RESOLVED: {IncidentState.CLOSED},
    IncidentState.CLOSED: set(),
    # failure/escalation branch
    IncidentState.TIMEOUT: {IncidentState.ESCALATED},
    IncidentState.ESCALATED: {IncidentState.FALLBACK_112},
    IncidentState.FALLBACK_112: {IncidentState.MANUAL_OPS},
    # manual_ops is a terminal-ish holding state; ops can force back into flow
    IncidentState.MANUAL_OPS: {
        IncidentState.DISPATCHED,   # re-dispatch after manual intervention
        IncidentState.ACKNOWLEDGED,  # ops manually confirms ack
        IncidentState.CLOSED,        # ops force-closes
    },
}

# States after which the incident is considered terminal (workers/schedulers stop polling)
TERMINAL_STATES = {IncidentState.CLOSED}

# Ack-required states: entering these starts an escalation timer (Module 26 escalation_worker)
ACK_TIMEOUT_STATES = {IncidentState.DISPATCHED}

# Default ack timeout in seconds per escalation stage (dispatched -> timeout -> escalated -> fallback_112)
ACK_TIMEOUT_SECONDS = 90
ESCALATION_TIMEOUT_SECONDS = 120
FALLBACK_TIMEOUT_SECONDS = 180


class InvalidTransitionError(Exception):
    def __init__(self, from_state: IncidentState, to_state: IncidentState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid dispatch transition: {from_state.value} -> {to_state.value}"
        )


def is_valid_transition(from_state: IncidentState, to_state: IncidentState) -> bool:
    return to_state in TRANSITIONS.get(from_state, set())


def is_terminal(state: IncidentState) -> bool:
    return state in TERMINAL_STATES

