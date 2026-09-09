"""
app/core/security.py

Implements every security primitive referenced across the codebase. Signatures below were
reverse-verified against actual call sites (not assumed):

    from app.core.security import get_current_user          # offline_sync.py, safezone.py,
                                                              #   tracking.py, trips.py, notifications.py
    from app.core.security import get_current_admin          # audit.py, admin.py, tracking.py
    from app.core.security import verify_internal_key         # internal.py, internal_dispatch.py,
                                                              #   authority_router.py, hospital_router.py
    from app.core.security import verify_partner_key          # authority_router.py, hospital_router.py
    from app.core.security import create_access_token         # auth_service.py -> create_access_token(user.id)

Usage patterns confirmed:
    user  = Depends(get_current_user)   -> user.id is accessed directly (trips.py, safezone.py, tracking.py)
    admin = Depends(get_current_admin)  -> admin.id is accessed directly (tracking.py patch_status)
    _     = Depends(verify_internal_key)  -> return value discarded, only raises on failure
    _     = Depends(verify_partner_key)   -> same
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.core import User

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT issuance (called by auth_service.verify_otp)
# ---------------------------------------------------------------------------
def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# End-user auth (OTP -> JWT). Used on every public route that needs a logged-in user.
# ---------------------------------------------------------------------------
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = _decode_token(creds.credentials)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Admin console auth. Same JWT, but role must be "admin" (see User.role, admin_service.py's
# `if actor.role != "admin"` check — that check becomes redundant once routes use this
# dependency, but is left in place in admin_service.py as defense in depth).
# ---------------------------------------------------------------------------
def get_current_admin(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(creds, db)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Server-to-server auth for /internal/* routes (Celery workers, ops scripts).
# Confirmed header name from scripts/e2e_smoke_test.py: "X-Internal-Key".
# Never exposed to the frontend / end users.
# ---------------------------------------------------------------------------
def verify_internal_key(x_internal_key: str = Header(default=None, alias="X-Internal-Key")) -> None:
    if not settings.INTERNAL_API_KEY or x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal key")


# ---------------------------------------------------------------------------
# Partner ack-webhook auth (hospitals / authorities calling back to acknowledge a
# dispatched route). B12 — confirmed "referenced, never defined anywhere" in m8-14's own
# README. No partner-key table exists in any delivered schema, so this is implemented
# against a per-partner shared-secret header compared to INTERNAL_API_KEY as an interim
# measure. ⚠️ ASSUMPTION — once you show me Module 2's hospitals/jurisdictions table
# columns, this should be upgraded to look up a per-partner key (e.g. hospitals.webhook_secret)
# instead of one shared secret, so a leaked key can be rotated per-partner.
# ---------------------------------------------------------------------------
def verify_partner_key(x_partner_key: str = Header(default=None, alias="X-Partner-Key")) -> None:
    if not settings.INTERNAL_API_KEY or x_partner_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid partner key")