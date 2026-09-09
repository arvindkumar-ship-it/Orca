import json
from pywebpush import webpush, WebPushException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings


def send_push(db: Session, user_id: str, title: str, body: str, full_screen: bool) -> dict:
    rows = db.execute(text("SELECT device_token FROM user_devices WHERE user_id = :uid AND push_enabled = true"),
                       {"uid": user_id}).mappings().all()
    if not rows:
        return {"ok": False, "error": "NO_PUSH_SUBSCRIPTION"}

    any_sent, last_error = False, ""
    for r in rows:
        try:
            webpush(
                subscription_info=json.loads(r["device_token"]),
                data=json.dumps({"title": title, "body": body, "full_screen": full_screen}),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
            )
            any_sent = True
        except WebPushException as e:
            last_error = str(e)
    return {"ok": any_sent} if any_sent else {"ok": False, "error": last_error}
