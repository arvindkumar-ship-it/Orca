"""Module 7 — Trip Planner: orchestrator (steps 1-14).
ASSUMPTION: TripPlan, TripRiskSnapshot models from Module 2C; redis_client/
celery_app as in prior modules."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from app.core.db import get_session              # ASSUMPTION
from app.models import TripPlan, TripRiskSnapshot  # ASSUMPTION
from app.redis_client import redis_client    # ASSUMPTION
from app.workers.celery_app import celery_app        # ASSUMPTION

from .risk import compute_trip_risk, recommend_alternative_beaches
from .advisory import generate_advisory

logger = logging.getLogger("trip_planner")
NOTIFY_CHANNEL_PREFIX = "notification_queue:enqueue"  # Module 13 consumes this


def create_trip_plan(user_id: str, beach_id: str, activity_type: str,
                      planned_from: datetime, planned_to: datetime) -> dict:
    """steps 1-4, 10-11: create plan, compute initial risk, save, subscribe to changes."""
    with get_session() as session:
        plan = TripPlan(
            user_id=user_id, beach_id=beach_id, activity_type=activity_type,
            planned_from=planned_from, planned_to=planned_to, status="active",
        )
        session.add(plan)
        session.flush()
        plan_id = str(plan.id)

        snapshot = _compute_and_save_snapshot(session, plan_id, beach_id, activity_type,
                                               planned_from, planned_to)
        session.commit()

    _subscribe_to_changes(plan_id, beach_id, activity_type)  # step 11
    logger.info("trip_planner.created plan_id=%s beach_id=%s verdict=%s",
                plan_id, beach_id, snapshot["recommendation"])
    return {"trip_plan_id": plan_id, **snapshot}


def _compute_and_save_snapshot(session, plan_id: str, beach_id: str, activity_type: str,
                                window_start: datetime, window_end: datetime) -> dict:
    result = compute_trip_risk(session, beach_id, activity_type, window_start, window_end)
    alternatives = recommend_alternative_beaches(session, beach_id, activity_type,
                                                  window_start, window_end) if result.worst_verdict == "unsafe" else []
    advisory = generate_advisory(result, alternatives)

    row = TripRiskSnapshot(
        trip_plan_id=plan_id,
        min_risk=min((p.risk_score for p in result.points), default=result.max_risk),
        max_risk=result.max_risk,
        recommendation=advisory,
        safe_window_start=window_start if result.worst_verdict == "safe" else None,
        safe_window_end=window_end if result.worst_verdict == "safe" else None,
        explanation={
            "worst_verdict": result.worst_verdict,
            "dangerous_slots": [(s.isoformat(), e.isoformat()) for s, e in result.dangerous_slots],
            "alternatives": alternatives,
        },
    )
    session.add(row)
    session.flush()

    return {
        "max_risk": result.max_risk, "worst_verdict": result.worst_verdict,
        "recommendation": advisory, "alternatives": alternatives,
    }


def _subscribe_to_changes(plan_id: str, beach_id: str, activity_type: str) -> None:
    """step 11: register plan against forecast-update signal (Module 6 publishes
    trip_planner:forecast_updated) — stored as a Redis set for the listener to fan out."""
    key = f"trip_subscriptions:{beach_id}:{activity_type}"
    redis_client.sadd(key, plan_id)


@celery_app.task(name="trip_planner.on_forecast_update", bind=True, max_retries=2)
def on_forecast_update(self, beach_id: str, activity_type: str):
    """step 12: recompute snapshots for every subscribed active plan; push notification
    if the recommendation materially changed (worsened)."""
    key = f"trip_subscriptions:{beach_id}:{activity_type}"
    plan_ids = redis_client.smembers(key)
    if not plan_ids:
        return {"checked": 0}

    updated = 0
    with get_session() as session:
        stmt = select(TripPlan).where(TripPlan.id.in_(plan_ids), TripPlan.status == "active")
        for plan in session.execute(stmt).scalars():
            prev = _latest_snapshot(session, str(plan.id))
            new_snap = _compute_and_save_snapshot(
                session, str(plan.id), beach_id, activity_type, plan.planned_from, plan.planned_to,
            )
            if prev and _worsened(prev, new_snap):
                _push_change_notification(str(plan.user_id), str(plan.id), new_snap)  # step 12
            updated += 1
        session.commit()
    return {"checked": updated}


def _latest_snapshot(session, plan_id: str) -> Optional[dict]:
    stmt = (
        select(TripRiskSnapshot)
        .where(TripRiskSnapshot.trip_plan_id == plan_id)
        .order_by(TripRiskSnapshot.computed_at.desc())
        .offset(1).limit(1)  # skip the row just inserted this call
    )
    row = session.execute(stmt).scalar_one_or_none()
    return {"max_risk": row.max_risk} if row else None


def _worsened(prev: dict, new: dict) -> bool:
    return new["max_risk"] - prev["max_risk"] >= 0.15  # same change threshold as Module 6


def _push_change_notification(user_id: str, plan_id: str, snapshot: dict) -> None:
    payload = {
        "user_id": user_id, "type": "trip_forecast_change", "priority": "high",
        "title": "Your trip forecast changed",
        "body": snapshot["recommendation"],
        "channel": "push", "trip_plan_id": plan_id,
    }
    redis_client.publish(NOTIFY_CHANNEL_PREFIX, json.dumps(payload, default=str))


def record_post_trip_feedback(trip_plan_id: str, user_id: str, feedback: dict) -> None:
    """step 14: post-trip feedback collection — stored on the plan's explanation trail."""
    with get_session() as session:
        plan = session.get(TripPlan, trip_plan_id)
        if plan is None or str(plan.user_id) != user_id:
            raise ValueError("trip plan not found for this user")
        plan.status = "completed"
        row = TripRiskSnapshot(
            trip_plan_id=trip_plan_id, min_risk=0, max_risk=0,
            recommendation="post_trip_feedback",
            explanation={"feedback": feedback, "submitted_at": datetime.now(timezone.utc).isoformat()},
        )
        session.add(row)
        session.commit()


def get_trip_history(user_id: str) -> list[dict]:
    """step 13: trip history."""
    with get_session() as session:
        stmt = select(TripPlan).where(TripPlan.user_id == user_id).order_by(TripPlan.created_at.desc())
        return [
            {"trip_plan_id": str(p.id), "beach_id": str(p.beach_id), "activity_type": p.activity_type,
             "status": p.status, "planned_from": p.planned_from.isoformat(), "planned_to": p.planned_to.isoformat()}
            for p in session.execute(stmt).scalars()
        ]
