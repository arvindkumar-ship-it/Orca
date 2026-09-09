"""ORCA — app/models/voyage_watch.py (NEW). Backs route_optimizer/watcher.py
— see that file's docstring for why this exists instead of a literal
grid-cell subscription."""
from __future__ import annotations
from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

from app.models.base import Base, uuid_pk


class VoyageWatch(Base):
    __tablename__ = "voyage_watches"
    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    marine_zone_id = Column(UUID(as_uuid=True), ForeignKey("marine_zones.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")  # 'active' | 'completed' | 'cancelled'
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
