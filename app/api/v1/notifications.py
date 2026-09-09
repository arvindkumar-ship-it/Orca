"""Module 23 — API Layer: Notifications (user-facing inbox)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError, ForbiddenError
from app.schemas.notification import NotificationListResponse, NotificationItem, NotificationReadResponse
from app.services import notification_inbox_service as svc

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = svc.list_notifications(db, user.id)
    return NotificationListResponse(items=[
        NotificationItem(id=n.id, type=n.type, title=n.title, body=n.body,
                          priority=n.priority, read=n.read_at is not None, created_at=n.sent_at)
        for n in items
    ])


@router.post("/{notification_id}/read", response_model=NotificationReadResponse)
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        n = svc.mark_read(db, notification_id, user.id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ForbiddenError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    return NotificationReadResponse(notification_id=n.id, status="read")
