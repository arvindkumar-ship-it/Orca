"""Assumes app.models.user.User (Module 2A) and app.services.sms_provider.send_sms(phone, body)
(Module 13/26) already exist. Uses passlib for code hashing + app.core.security.create_access_token
for JWT issuance (consistent with existing JWT+bcrypt auth pattern)."""
import random
import uuid
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.security import create_access_token
from app.models.core import User
from app.models.otp import OTPCode
from app.services.sms_provider import send_sms

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
OTP_TTL_SEC = 300
MAX_ATTEMPTS = 5


def request_otp(db: Session, phone: str) -> int:
    code = f"{random.randint(0, 999999):06d}"
    otp = OTPCode(
        phone=phone, code_hash=pwd_ctx.hash(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=OTP_TTL_SEC),
    )
    db.add(otp)
    db.commit()
    send_sms(phone, f"Your Coastal Safety verification code is {code}. Valid for 5 minutes.")
    return OTP_TTL_SEC


def verify_otp(db: Session, phone: str, code: str) -> tuple[str, uuid.UUID]:
    otp = (
        db.query(OTPCode)
        .filter(OTPCode.phone == phone, OTPCode.consumed_at.is_(None))
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not otp or otp.expires_at < datetime.now(timezone.utc):
        raise ValidationError("OTP expired or not found")
    if otp.attempts >= MAX_ATTEMPTS:
        raise ValidationError("Too many attempts, request a new OTP")
    if not pwd_ctx.verify(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise ValidationError("Incorrect OTP")

    otp.consumed_at = datetime.now(timezone.utc)
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone)
        db.add(user)
        db.flush()
    db.commit()

    token = create_access_token(user.id)
    return token, user.id
