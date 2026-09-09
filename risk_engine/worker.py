"""Module 5 — Risk Engine: worker. Subscribes to `risk_engine:recompute_trigger`
(published by Module 3/4's persistence.py) and recomputes affected beach/activity
risk scores. ASSUMPTION: celery_app from app.celery_app, redis_client from
app.redis_client (same as Module 3's ingestion_worker.py)."""
from __future__ import annotations
import json
import logging

from app.workers.celery_app import celery_app       # ASSUMPTION
from app.redis_client import redis_client   # ASSUMPTION
from app.core.db import get_session              # ASSUMPTION
from app.models import BeachActivityProfile  # ASSUMPTION
from sqlalchemy import select

from risk_engine.engine import compute_and_store_risk

logger = logging.getLogger("risk_engine.worker")
TRIGGER_CHANNEL = "risk_engine:recompute_trigger"


@celery_app.task(name="risk_engine.recompute_for_beach", bind=True, max_retries=3)
def recompute_for_beach(self, beach_id: str):
    """Recompute risk for every active activity_type on a beach."""
    with get_session() as session:
        stmt = select(BeachActivityProfile.activity_type).where(
            BeachActivityProfile.beach_id == beach_id,
            BeachActivityProfile.active.is_(True),
        )
        activity_types = [r[0] for r in session.execute(stmt).all()]

    results = []
    for activity_type in activity_types:
        res = compute_and_store_risk(beach_id, activity_type)
        if res:
            results.append(res)
    return results


def listen_for_triggers() -> None:  # pragma: no cover — long-running process entrypoint
    """Run as a standalone process (not a Celery task) subscribed to Redis pub/sub;
    dispatches Celery tasks so recompute work doesn't block the listener."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(TRIGGER_CHANNEL)
    logger.info("risk_engine.worker.listening channel=%s", TRIGGER_CHANNEL)

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            payload = json.loads(message["data"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("risk_engine.worker.bad_message data=%s", message.get("data"))
            continue

        beach_id = payload.get("beach_id")
        if beach_id is None and payload.get("geometry"):
            # hazard alert without a direct beach_id — Module 5B enhancement: resolve
            # all beaches intersecting the hazard geometry. Not implemented here;
            # flagged rather than guessed — tell me if you want beach-set resolution
            # from a hazard polygon in this same trigger path.
            logger.warning("risk_engine.worker.hazard_trigger_no_beach_id payload=%s", payload)
            continue

        if beach_id:
            recompute_for_beach.delay(beach_id)
