import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.incident import NotificationQueue


def list_notifications(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[NotificationQueue]:
    return (
        db.query(NotificationQueue)
        .filter(NotificationQueue.user_id == user_id, NotificationQueue.status == "sent")
        .order_by(NotificationQueue.sent_at.desc())
        .limit(limit)
        .all()
    )


def mark_read(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> NotificationQueue:
    n = db.query(NotificationQueue).filter(NotificationQueue.id == notification_id).first()
    if not n:
        raise NotFoundError("Notification not found")
    if n.user_id != user_id:
        raise ForbiddenError("Not your notification")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n
