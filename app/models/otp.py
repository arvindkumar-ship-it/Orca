"""otp_codes: minimal addition to support POST /v1/auth/otp/* — no such table existed in
Module 2A-2D; everything else here (hospitals, jurisdictions, beaches, safe_zones,
beach_activity_profiles) reuses the exact models already built in Module 1/2B/2C."""
from sqlalchemy import Column, String, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    phone = Column(String, nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
