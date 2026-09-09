# B11 — extracted from Module 20-26's admin.py. That file had TWO routers in one:
# admin_router (CRUD, discarded — superseded by Module 17's richer version below) and
# auth_router (OTP, genuinely new, kept here as its own file). Already sync (verified —
# Module 20-26 was sync throughout, no B1 conversion needed for this one).

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import ValidationError
from app.schemas.admin import OTPRequest, OTPRequestResponse, OTPVerify, OTPVerifyResponse, LogoutResponse
from app.services import auth_service

auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])


@auth_router.post("/otp/request", response_model=OTPRequestResponse)
def otp_request(payload: OTPRequest, db: Session = Depends(get_db)):
    ttl = auth_service.request_otp(db, payload.phone)
    return OTPRequestResponse(phone=payload.phone, status="sent", expires_in_sec=ttl)


@auth_router.post("/otp/verify", response_model=OTPVerifyResponse)
def otp_verify(payload: OTPVerify, db: Session = Depends(get_db)):
    try:
        token, user_id = auth_service.verify_otp(db, payload.phone, payload.code)
    except ValidationError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
    return OTPVerifyResponse(access_token=token, user_id=user_id)


@auth_router.post("/logout", response_model=LogoutResponse)
def logout():
    # stateless JWT — client discards token; add to a blocklist here later if needed.
    return LogoutResponse()