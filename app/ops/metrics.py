"""
app/ops/metrics.py — one metric per Module 32 checklist item.
Call these from the existing modules at the noted integration points;
this file only defines the instruments, it doesn't rewrite those modules.

Integration points (wire in as a one-line call, do not restructure the caller):
- ingestion_worker (Module 26)            -> observe_ingestion_latency()
- DispatchStateMachine.transition()       -> observe_dispatch_latency() on entering 'dispatched'
                                              observe_ack_latency() on entering 'acknowledged'
- incident_routes write with ack_status='failed' -> inc_failed_route()
- geospatial QA job (Module 1 step 11)    -> set_stale_geodata()
- ops false-alert close (reason='false_alert') -> inc_false_positive()
- escalation_worker fallback_112 branch   -> inc_missed_alert()
- frontend crash reporter (new endpoint)  -> inc_app_crash()
- SOS trigger payload (battery_pct field) -> observe_battery_at_trigger()
- offline_sync_queue insert               -> inc_network_failure()
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

registry = CollectorRegistry()

ingestion_latency_seconds = Histogram(
    "coastal_ingestion_latency_seconds",
    "Time from source observation to hazard_alerts row created",
    buckets=(5, 15, 30, 60, 120, 300, 600),
    registry=registry,
)

dispatch_latency_seconds = Histogram(
    "coastal_dispatch_latency_seconds",
    "Time from incident created to dispatched",
    buckets=(1, 3, 5, 10, 20, 30, 60),
    registry=registry,
)

acknowledgement_latency_seconds = Histogram(
    "coastal_ack_latency_seconds",
    "Time from dispatched to acknowledged",
    buckets=(5, 15, 30, 60, 90, 120, 300),
    registry=registry,
)

failed_routes_total = Counter(
    "coastal_failed_routes_total",
    "incident_routes rows that ended in ack_status=failed",
    ["target_type"],
    registry=registry,
)

stale_geodata_rows = Gauge(
    "coastal_stale_geodata_rows",
    "Spatial entities whose last field-verification exceeds policy age",
    ["entity_type"],
    registry=registry,
)

false_positives_total = Counter(
    "coastal_false_positives_total",
    "Incidents closed with reason=false_alert",
    registry=registry,
)

missed_alerts_total = Counter(
    "coastal_missed_alerts_total",
    "Incidents that fell through to fallback_112 (primary responders missed it)",
    registry=registry,
)

app_crashes_total = Counter(
    "coastal_app_crashes_total",
    "Client-reported crashes",
    ["platform"],
    registry=registry,
)

network_failures_total = Counter(
    "coastal_network_failures_total",
    "offline_sync_queue insertions (client detected it could not reach the API)",
    registry=registry,
)

battery_at_sos_trigger_pct = Histogram(
    "coastal_battery_at_sos_trigger_pct",
    "Device battery percent at the moment SOS was triggered — proxy for background-tracking drain",
    buckets=(5, 10, 20, 30, 50, 70, 100),
    registry=registry,
)


def observe_ingestion_latency(seconds: float) -> None:
    ingestion_latency_seconds.observe(seconds)


def observe_dispatch_latency(seconds: float) -> None:
    dispatch_latency_seconds.observe(seconds)


def observe_ack_latency(seconds: float) -> None:
    acknowledgement_latency_seconds.observe(seconds)


def inc_failed_route(target_type: str) -> None:
    failed_routes_total.labels(target_type=target_type).inc()


def set_stale_geodata(entity_type: str, count: int) -> None:
    stale_geodata_rows.labels(entity_type=entity_type).set(count)


def inc_false_positive() -> None:
    false_positives_total.inc()


def inc_missed_alert() -> None:
    missed_alerts_total.inc()


def inc_app_crash(platform: str) -> None:
    app_crashes_total.labels(platform=platform).inc()


def inc_network_failure() -> None:
    network_failures_total.inc()


def observe_battery_at_trigger(pct: float) -> None:
    battery_at_sos_trigger_pct.observe(pct)


def render_metrics() -> bytes:
    return generate_latest(registry)
