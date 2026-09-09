from __future__ import annotations
import logging
from celery import shared_task
from app.core.db import SessionLocal
from app.models.geospatial import Beach
from risk_engine.engine import compute_and_store_risk

logger = logging.getLogger(__name__)

# ⚠️ ASSUMPTION — activity types not confirmed from a real source; using common set.
ACTIVITY_TYPES = ["swimming", "surfing", "boating"]


@shared_task(name="workers.risk.recompute_all")
def recompute_all() -> dict:
    db = SessionLocal()
    try:
        beaches = db.query(Beach).filter(Beach.active == True).all()
        updated = 0
        for beach in beaches:
            for activity in ACTIVITY_TYPES:
                result = compute_and_store_risk(str(beach.id), activity)
                if result:
                    updated += 1
        db.commit()
        return {"beaches_updated": updated}
    except Exception:
        db.rollback()
        logger.exception("risk_worker.recompute_failed")
        raise
    finally:
        db.close()