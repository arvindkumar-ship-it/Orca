# """
# Module 20 service layer — Trip Planning.
# Implements Module 7 formula: R_trip = max(R(b,a,t)) over the planned window (max, not avg).

# Depends on interfaces already built in earlier modules (0-19):
# - app.services.risk_engine.get_or_compute_risk(db, beach_id, activity_type, forecast_time)
#     -> object with .risk_score (float 0-1), .verdict (str), .explanation (dict), .hard_override_reason
#   (built in Module 5, exposed via Module 19 GET /beaches/{id}/risk)
# - app.services.forecast_engine.get_forecast_times(db, beach_id, from_time, to_time)
#     -> ordered list[datetime] of available forecast_time slots in the window
#   (built in Module 6, exposed via Module 19 GET /beaches/{id}/forecast)
# - app.core.audit.log_audit_event(db, event_type, entity_type, entity_id, actor_type, actor_id, payload)
#   (Module 18)
# - app.services.notification_service.enqueue_notification(db, user_id, type, priority, title, body, channel, incident_report_id=None)
#   (Module 13 — writes to notification_queue; Module 26 worker delivers it)
# - app.models.beach.Beach (Module 1/2B)

# If any of these differ in real signature, only this file's import block + call sites need adjusting —
# the trip_plans/trip_risk_snapshots schema and Module 20 API contract stay untouched.
# """
# import uuid
# from datetime import timedelta
# from typing import Optional

# from sqlalchemy.orm import Session

# from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
# from app.core.audit import log_audit_event
# from app.models.geospatial import Beach
# from app.models.forecast_risk import TripPlan, TripRiskSnapshot, TripStatus, TripRecommendation
# from risk_engine.engine import get_or_compute_risk
# from forecast_engine.engine import get_forecast_times
# from app.services.notification_service import enqueue

# SAFE_THRESHOLD = 0.33
# UNSAFE_THRESHOLD = 0.66
# MATERIAL_CHANGE_DELTA = 0.15


# def _recommendation_for(max_risk: float) -> str:
#     if max_risk >= UNSAFE_THRESHOLD:
#         return TripRecommendation.AVOID_TRIP
#     if max_risk >= SAFE_THRESHOLD:
#         return TripRecommendation.CAUTION
#     return TripRecommendation.GO


# def _slot_label(t) -> str:
#     end = t + timedelta(hours=1)
#     return f"{t.strftime('%H:%M')}-{end.strftime('%H:%M')}"


# def _run_full_scan(db: Session, trip: TripPlan) -> TripRiskSnapshot:
#     """Module 7 steps 4-8: fetch forecast curve, compute max risk, detect danger slots,
#     find safe windows, generate advisory."""
#     slot_times = get_forecast_times(db, trip.beach_id, trip.planned_from, trip.planned_to)
#     if not slot_times:
#         raise ValidationError("No forecast data available for the requested trip window yet")

#     risks = []
#     for t in slot_times:
#         result = get_or_compute_risk(db, trip.beach_id, trip.activity_type, t)
#         risks.append((t, float(result.risk_score), result.verdict))

#     max_risk = max(r for _, r, _ in risks)
#     min_risk = min(r for _, r, _ in risks)
#     recommendation = _recommendation_for(max_risk)

#     danger_slots = [_slot_label(t) for t, r, _ in risks if r >= UNSAFE_THRESHOLD]

#     safe_window_start, safe_window_end = None, None
#     run_start = None
#     for t, r, _ in risks:
#         if r < SAFE_THRESHOLD:
#             if run_start is None:
#                 run_start = t
#             safe_window_end = t + timedelta(hours=1)
#         else:
#             if run_start is not None and safe_window_start is None:
#                 safe_window_start = run_start
#                 # keep first safe run only, matching module example (single window)
#             run_start = None
#     if run_start is not None and safe_window_start is None:
#         safe_window_start = run_start

#     if safe_window_start is None:
#         safe_window_end = None

#     snapshot = TripRiskSnapshot(
#         trip_plan_id=trip.id,
#         min_risk=min_risk,
#         max_risk=max_risk,
#         recommendation=recommendation,
#         safe_window_start=safe_window_start,
#         safe_window_end=safe_window_end,
#         explanation={"danger_slots": danger_slots},
#     )
#     db.add(snapshot)
#     db.flush()
#     return snapshot


# def _maybe_notify_change(db: Session, trip: TripPlan, prev: Optional[TripRiskSnapshot], curr: TripRiskSnapshot) -> bool:
#     if prev is None:
#         changed = True
#     else:
#         changed = (
#             prev.recommendation != curr.recommendation
#             or abs(float(prev.max_risk or 0) - float(curr.max_risk or 0)) >= MATERIAL_CHANGE_DELTA
#         )
#     if changed and trip.status == TripStatus.ACTIVE:
#         enqueue_notification(
#             db,
#             user_id=trip.user_id,
#             type="trip_risk_change",
#             priority="high" if curr.recommendation == TripRecommendation.AVOID_TRIP else "normal",
#             title="Trip advisory updated",
#             body=f"Your trip on beach {trip.beach_id} is now: {curr.recommendation.replace('_', ' ')}",
#             channel="push",
#         )
#     return changed


# def create_trip(db: Session, user_id: uuid.UUID, beach_id: uuid.UUID, activity_type: str,
#                  planned_from, planned_to) -> TripPlan:
#     beach = db.query(Beach).filter(Beach.id == beach_id, Beach.active.is_(True)).first()
#     if not beach:
#         raise NotFoundError("Beach not found")
#     if planned_to <= planned_from:
#         raise ValidationError("planned_to must be after planned_from")

#     trip = TripPlan(
#         user_id=user_id,
#         beach_id=beach_id,
#         activity_type=activity_type,
#         planned_from=planned_from,
#         planned_to=planned_to,
#         status=TripStatus.ACTIVE,
#     )
#     db.add(trip)
#     db.flush()  # get trip.id before scan

#     try:
#         snapshot = _run_full_scan(db, trip)
#         _maybe_notify_change(db, trip, None, snapshot)
#     except ValidationError:
#         # no forecast yet — trip still created, first rescan will populate risk
#         snapshot = None

#     log_audit_event(
#         db, event_type="trip.created", entity_type="trip_plan", entity_id=trip.id,
#         actor_type="user", actor_id=user_id,
#         payload={"beach_id": str(beach_id), "activity_type": activity_type},
#     )
#     db.commit()
#     db.refresh(trip)
#     return trip


# def get_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripPlan:
#     trip = db.query(TripPlan).filter(TripPlan.id == trip_id).first()
#     if not trip:
#         raise NotFoundError("Trip not found")
#     if trip.user_id != user_id:
#         raise ForbiddenError("Not your trip")
#     return trip


# def latest_snapshot(db: Session, trip_id: uuid.UUID) -> Optional[TripRiskSnapshot]:
#     return (
#         db.query(TripRiskSnapshot)
#         .filter(TripRiskSnapshot.trip_plan_id == trip_id)
#         .order_by(TripRiskSnapshot.computed_at.desc())
#         .first()
#     )


# def advisory_label(snapshot: Optional[TripRiskSnapshot]) -> str:
#     if snapshot is None:
#         return "not advised"
#     mapping = {
#         TripRecommendation.GO: "go",
#         TripRecommendation.CAUTION: "caution advised",
#         TripRecommendation.AVOID_TRIP: "not advised",
#     }
#     return mapping.get(snapshot.recommendation, "not advised")


# def get_trip_risk(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripRiskSnapshot:
#     trip = get_trip(db, trip_id, user_id)
#     snap = latest_snapshot(db, trip.id)
#     if snap is None:
#         snap = _run_full_scan(db, trip)
#         db.commit()
#         db.refresh(snap)
#     return snap


# def rescan_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> tuple[TripPlan, bool]:
#     """Module 20 POST /trips/{id}/rescan — recompute on updated source data."""
#     trip = get_trip(db, trip_id, user_id)
#     if trip.status != TripStatus.ACTIVE:
#         raise ValidationError("Cannot rescan a non-active trip")

#     prev = latest_snapshot(db, trip.id)
#     curr = _run_full_scan(db, trip)
#     risk_changed = _maybe_notify_change(db, trip, prev, curr)

#     log_audit_event(
#         db, event_type="trip.rescanned", entity_type="trip_plan", entity_id=trip.id,
#         actor_type="user", actor_id=user_id,
#         payload={"risk_changed": risk_changed, "max_risk": float(curr.max_risk or 0)},
#     )
#     db.commit()
#     return trip, risk_changed


# def bulk_rescan_active_trips(db: Session) -> int:
#     """Module 26 risk_worker: recompute every active trip after new forecast data lands."""
#     trips = db.query(TripPlan).filter(TripPlan.status == TripStatus.ACTIVE).all()
#     rescanned = 0
#     for trip in trips:
#         try:
#             prev = latest_snapshot(db, trip.id)
#             curr = _run_full_scan(db, trip)
#             _maybe_notify_change(db, trip, prev, curr)
#             rescanned += 1
#         except ValidationError:
#             continue  # no forecast for this beach/window yet
#     db.commit()
#     return rescanned


# def cancel_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripPlan:
#     trip = get_trip(db, trip_id, user_id)
#     if trip.status == TripStatus.CANCELLED:
#         return trip
#     trip.status = TripStatus.CANCELLED
#     log_audit_event(
#         db, event_type="trip.cancelled", entity_type="trip_plan", entity_id=trip.id,
#         actor_type="user", actor_id=user_id, payload={},
#     )
#     db.commit()
#     db.refresh(trip)
#     return trip























































"""
Module 20 service layer — Trip Planning.

NOTE (deviation from original Module 7 spec): the real risk_engine/forecast_engine
functions do not accept a db session or a (from_time, to_time) window and do not return
a per-slot list. They are:
  - risk_engine.engine.compute_and_store_risk(beach_id: str, activity_type: str) -> Optional[dict]
      Computes + persists ONE current risk snapshot (no forecast_time param).
  - forecast_engine.engine.compute_forecast_outlook(beach_id: str, activity_type: str) -> dict
      Returns a single outlook dict: current_verdict, current_risk, window_3h, window_12h,
      safe_window_start/end (ISO strings), no_go_windows (list of ISO-string tuples), confidence.

So true "max risk across the exact planned_from/planned_to window" is not directly available.
This implementation approximates max_risk from current_risk + the worse of window_3h/window_12h,
and reuses the engine's own safe_window / no_go_windows instead of recomputing per-slot.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.core.audit import log_audit_event
from app.models.geospatial import Beach
from app.models.forecast_risk import TripPlan, TripRiskSnapshot, TripStatus, TripRecommendation
from risk_engine.engine import compute_and_store_risk
from forecast_engine.engine import compute_forecast_outlook
from app.services.notification_service import enqueue

SAFE_THRESHOLD = 0.33
UNSAFE_THRESHOLD = 0.66
MATERIAL_CHANGE_DELTA = 0.15

_VERDICT_RISK_FLOOR = {
    "safe": 0.0,
    "caution": SAFE_THRESHOLD,
    "unsafe": UNSAFE_THRESHOLD,
}


def _recommendation_for(max_risk: float) -> str:
    if max_risk >= UNSAFE_THRESHOLD:
        return TripRecommendation.AVOID_TRIP
    if max_risk >= SAFE_THRESHOLD:
        return TripRecommendation.CAUTION
    return TripRecommendation.GO


def _parse_iso(value) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _run_full_scan(db: Session, trip: TripPlan) -> TripRiskSnapshot:
    """Refresh current risk, then pull the engine's own outlook (safe window /
    no-go windows / 3h-12h verdicts) instead of looping per forecast slot —
    the real engines don't expose a per-slot API. See module docstring."""
    beach_id_str = str(trip.beach_id)

    compute_and_store_risk(beach_id_str, trip.activity_type)  # refresh persisted current score
    outlook = compute_forecast_outlook(beach_id_str, trip.activity_type)

    if not outlook or outlook.get("current_verdict") in (None, "unknown"):
        raise ValidationError("No forecast data available for the requested trip window yet")

    current_risk = float(outlook.get("current_risk") or 0.0)
    worst_verdict = outlook.get("window_12h") or outlook.get("window_3h") or outlook.get("current_verdict")
    max_risk = max(current_risk, _VERDICT_RISK_FLOOR.get(worst_verdict, 0.0))
    min_risk = current_risk
    recommendation = _recommendation_for(max_risk)

    danger_slots = [
        f"{s[:16]} to {e[:16]}" for s, e in outlook.get("no_go_windows", [])
    ]

    safe_window_start = _parse_iso(outlook.get("safe_window_start"))
    safe_window_end = _parse_iso(outlook.get("safe_window_end"))

    snapshot = TripRiskSnapshot(
        trip_plan_id=trip.id,
        min_risk=min_risk,
        max_risk=max_risk,
        recommendation=recommendation,
        safe_window_start=safe_window_start,
        safe_window_end=safe_window_end,
        explanation={
            "danger_slots": danger_slots,
            "outlook_confidence": outlook.get("confidence"),
            "window_3h": outlook.get("window_3h"),
            "window_12h": outlook.get("window_12h"),
        },
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _maybe_notify_change(db: Session, trip: TripPlan, prev: Optional[TripRiskSnapshot], curr: TripRiskSnapshot) -> bool:
    if prev is None:
        changed = True
    else:
        changed = (
            prev.recommendation != curr.recommendation
            or abs(float(prev.max_risk or 0) - float(curr.max_risk or 0)) >= MATERIAL_CHANGE_DELTA
        )
    if changed and trip.status == TripStatus.ACTIVE:
        enqueue(
            db,
            user_id=trip.user_id,
            type="trip_risk_change",
            priority="high" if curr.recommendation == TripRecommendation.AVOID_TRIP else "normal",
            title="Trip advisory updated",
            body=f"Your trip on beach {trip.beach_id} is now: {curr.recommendation.replace('_', ' ')}",
        )
    return changed


def create_trip(db: Session, user_id: uuid.UUID, beach_id: uuid.UUID, activity_type: str,
                 planned_from, planned_to) -> TripPlan:
    beach = db.query(Beach).filter(Beach.id == beach_id, Beach.active.is_(True)).first()
    if not beach:
        raise NotFoundError("Beach not found")
    if planned_to <= planned_from:
        raise ValidationError("planned_to must be after planned_from")

    trip = TripPlan(
        user_id=user_id,
        beach_id=beach_id,
        activity_type=activity_type,
        planned_from=planned_from,
        planned_to=planned_to,
        status=TripStatus.ACTIVE,
    )
    db.add(trip)
    db.flush()  # get trip.id before scan

    try:
        snapshot = _run_full_scan(db, trip)
        _maybe_notify_change(db, trip, None, snapshot)
    except ValidationError:
        # no forecast yet — trip still created, first rescan will populate risk
        snapshot = None

    log_audit_event(
        db, event_type="trip.created", entity_type="trip_plan", entity_id=trip.id,
        actor_type="user", actor_id=user_id,
        payload={"beach_id": str(beach_id), "activity_type": activity_type},
    )
    db.commit()
    db.refresh(trip)
    return trip


def get_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripPlan:
    trip = db.query(TripPlan).filter(TripPlan.id == trip_id).first()
    if not trip:
        raise NotFoundError("Trip not found")
    if trip.user_id != user_id:
        raise ForbiddenError("Not your trip")
    return trip


def latest_snapshot(db: Session, trip_id: uuid.UUID) -> Optional[TripRiskSnapshot]:
    return (
        db.query(TripRiskSnapshot)
        .filter(TripRiskSnapshot.trip_plan_id == trip_id)
        .order_by(TripRiskSnapshot.computed_at.desc())
        .first()
    )


def advisory_label(snapshot: Optional[TripRiskSnapshot]) -> str:
    if snapshot is None:
        return "not advised"
    mapping = {
        TripRecommendation.GO: "go",
        TripRecommendation.CAUTION: "caution advised",
        TripRecommendation.AVOID_TRIP: "not advised",
    }
    return mapping.get(snapshot.recommendation, "not advised")


def get_trip_risk(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripRiskSnapshot:
    trip = get_trip(db, trip_id, user_id)
    snap = latest_snapshot(db, trip.id)
    if snap is None:
        snap = _run_full_scan(db, trip)
        db.commit()
        db.refresh(snap)
    return snap


def rescan_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> tuple[TripPlan, bool]:
    """Module 20 POST /trips/{id}/rescan — recompute on updated source data."""
    trip = get_trip(db, trip_id, user_id)
    if trip.status != TripStatus.ACTIVE:
        raise ValidationError("Cannot rescan a non-active trip")

    prev = latest_snapshot(db, trip.id)
    curr = _run_full_scan(db, trip)
    risk_changed = _maybe_notify_change(db, trip, prev, curr)

    log_audit_event(
        db, event_type="trip.rescanned", entity_type="trip_plan", entity_id=trip.id,
        actor_type="user", actor_id=user_id,
        payload={"risk_changed": risk_changed, "max_risk": float(curr.max_risk or 0)},
    )
    db.commit()
    return trip, risk_changed


def bulk_rescan_active_trips(db: Session) -> int:
    """Module 26 risk_worker: recompute every active trip after new forecast data lands."""
    trips = db.query(TripPlan).filter(TripPlan.status == TripStatus.ACTIVE).all()
    rescanned = 0
    for trip in trips:
        try:
            prev = latest_snapshot(db, trip.id)
            curr = _run_full_scan(db, trip)
            _maybe_notify_change(db, trip, prev, curr)
            rescanned += 1
        except ValidationError:
            continue  # no forecast for this beach/window yet
    db.commit()
    return rescanned


def cancel_trip(db: Session, trip_id: uuid.UUID, user_id: uuid.UUID) -> TripPlan:
    trip = get_trip(db, trip_id, user_id)
    if trip.status == TripStatus.CANCELLED:
        return trip
    trip.status = TripStatus.CANCELLED
    log_audit_event(
        db, event_type="trip.cancelled", entity_type="trip_plan", entity_id=trip.id,
        actor_type="user", actor_id=user_id, payload={},
    )
    db.commit()
    db.refresh(trip)
    return trip