"""
ORCA — GENERALIZE of trip_planner/planner.py's Celery subscribe/notify
pattern -> route_optimizer/watcher.py.

DEVIATION FROM THE SPEC'S LITERAL WORDING, STATED PLAINLY: the build spec
says "keyed by grid-cell instead of beach_id". A raw A* grid cell has no
persistent identity worth subscribing to — route_optimizer's grid is
rebuilt fresh per /route/plan request (RiskGrid in optimizer.py) and
nothing persists a "this cell is being watched" row. What CAN be watched,
consistent with trip_planner's actual mechanism (subscribe a plan to a
beach_id+activity_type, get notified when that beach's forecast changes),
is a VoyageWatch keyed by marine_zone_id+activity_type — a user (or an
active route's destination zone) registers interest, exactly like a
TripPlan did, and gets notified when that zone's risk materially worsens.
This is the same mechanism, applied to the nearest real identity ORCA
actually has for a point in the water (the calibration zone from
risk_engine/point_scoring.py), not a literal ungrounded grid index.

Needs a new `voyage_watches` table (mirrors `trip_plans`, drop the
per-trip fields that don't apply — beach_id->marine_zone_id, no
planned_from/planned_to since a voyage watch isn't a single dated trip).
Not yet migrated — add alongside chat_sessions in the next migration pass.
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from sqlalchemy import select
from app.core.db import get_session
from app.redis_client import redis_client
from app.workers.celery_app import celery_app

from risk_engine.engine import compute_and_store_risk

logger = logging.getLogger("route_optimizer.watcher")
NOTIFY_CHANNEL_PREFIX = "notification_queue:enqueue"
WORSENED_THRESHOLD = 0.15  # same change threshold trip_planner used


def subscribe_watch(marine_zone_id: str, activity_type: str, watch_id: str) -> None:
    key = f"voyage_watch_subscriptions:{marine_zone_id}:{activity_type}"
    redis_client.sadd(key, watch_id)


@celery_app.task(name="route_optimizer.on_zone_forecast_update", bind=True, max_retries=2)
def on_zone_forecast_update(self, marine_zone_id: str, activity_type: str):
    """Same shape as trip_planner.on_forecast_update: recompute risk for
    every watch subscribed to this zone+activity, notify if it worsened."""
    from app.models.voyage_watch import VoyageWatch  # imported lazily — see this module's docstring re: not-yet-migrated table

    key = f"voyage_watch_subscriptions:{marine_zone_id}:{activity_type}"
    watch_ids = redis_client.smembers(key)
    if not watch_ids:
        return {"checked": 0}

    updated = 0
    with get_session() as session:
        stmt = select(VoyageWatch).where(VoyageWatch.id.in_(watch_ids), VoyageWatch.status == "active")
        for watch in session.execute(stmt).scalars():
            prev = _latest_risk(session, marine_zone_id, activity_type)
            new_result = compute_and_store_risk(marine_zone_id, activity_type)
            if new_result is None:
                continue
            if prev is not None and (new_result["risk_score"] - prev) >= WORSENED_THRESHOLD:
                _push_change_notification(str(watch.user_id), marine_zone_id, new_result)
            updated += 1
        session.commit()
    return {"checked": updated}


def _latest_risk(session, marine_zone_id: str, activity_type: str) -> Optional[float]:
    from app.models.forecast_risk import ZoneRiskScore
    stmt = (
        select(ZoneRiskScore.risk_score)
        .where(ZoneRiskScore.marine_zone_id == marine_zone_id, ZoneRiskScore.activity_type == activity_type)
        .order_by(ZoneRiskScore.computed_at.desc()).offset(1).limit(1)  # skip the row just inserted this call
    )
    return session.execute(stmt).scalar_one_or_none()


def _push_change_notification(user_id: str, marine_zone_id: str, result: dict) -> None:
    payload = {
        "user_id": user_id, "type": "zone_forecast_change", "priority": "high",
        "title": "Sea conditions changed at your watched zone",
        "body": f"Risk verdict is now {result['verdict']} (score {result['risk_score']:.2f}).",
        "channel": "push", "marine_zone_id": marine_zone_id,
    }
    redis_client.publish(NOTIFY_CHANNEL_PREFIX, json.dumps(payload, default=str))
