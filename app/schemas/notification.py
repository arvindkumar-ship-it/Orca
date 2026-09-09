import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    priority: str
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]


class NotificationReadResponse(BaseModel):
    notification_id: uuid.UUID
    status: str
