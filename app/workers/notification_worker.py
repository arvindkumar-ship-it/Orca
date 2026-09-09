"""
app/workers/notification_worker.py
Beat calls flush_queue() every 10s — drains NotificationQueue rows (B5:
locale/full_screen/delivery_meta columns) and dispatches via SMS/push provider.

ASSUMPTION: app.services.notification_service exposes flush_pending(db) —
real notification service file not verified, function name guessed.
"""
from __future__ import annotations
import logging
from celery import shared_task
from app.core.db import SessionLocal
#from app.services.notification_service import flush_pending  # ASSUMPTION — verify
from app.services.notification_service import enqueue, deliver
from app.models.incident import NotificationQueue

logger = logging.getLogger(__name__)


@shared_task(name="workers.notification.flush_queue")
def flush_queue() -> dict:
    db = SessionLocal()
    try:
        pending = db.query(NotificationQueue).filter(NotificationQueue.status == "queued").all()
        sent, failed = 0, 0
        for n in pending:
            ok = deliver(db, n)
            n.status = "sent" if ok else "failed"
            if ok:
                sent += 1
            else:
                failed += 1
        db.commit()
        return {"sent": sent, "failed": failed}
    finally:
        db.close()