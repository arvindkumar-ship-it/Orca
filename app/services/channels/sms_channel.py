# import httpx
# from app.core.config import settings


# def send_sms(phone: str, body: str) -> dict:
#     if not phone:
#         return {"ok": False, "error": "NO_PHONE_ON_FILE"}
#     try:
#         resp = httpx.post(settings.SMS_GATEWAY_URL, json={"to": phone, "message": body[:160]},
#                            headers={"Authorization": f"Bearer {settings.SMS_GATEWAY_KEY}"}, timeout=10)
#         if resp.status_code >= 400:
#             return {"ok": False, "error": f"SMS_GATEWAY_{resp.status_code}"}
#         return {"ok": True, "ref": resp.json().get("messageId")}
#     except httpx.HTTPError as e:
#         return {"ok": False, "error": str(e)}





"""
Fast2SMS integration (route "q" — Quick Transactional, no DLT registration needed).
API docs: https://docs.fast2sms.com — endpoint/payload verified against
https://www.fast2sms.com/free-sms-api-gateway (official sample as of 2026-08-22).

Fast2SMS expects numbers as plain 10-digit Indian mobile numbers (no "+91" prefix,
no spaces/dashes). If phone numbers in your DB are stored with "+91" or spaces,
strip them before calling send_sms() — not done here since I don't know your
actual stored format and won't guess it.
"""
import httpx
from app.core.config import settings


def send_sms(phone: str, body: str) -> dict:
    if not phone:
        return {"ok": False, "error": "NO_PHONE_ON_FILE"}
    try:
        resp = httpx.post(
            settings.SMS_GATEWAY_URL,
            json={"message": body[:160], "route": "q", "numbers": phone, "flash": "0"},
            headers={
                "authorization": settings.SMS_GATEWAY_KEY,
                "accept": "*/*",
                "content-type": "application/json",
            },
            timeout=10,
        )
        data = resp.json()
        if resp.status_code >= 400 or data.get("return") is not True:
            return {"ok": False, "error": data.get("message") or f"SMS_GATEWAY_{resp.status_code}"}
        return {"ok": True, "ref": data.get("request_id")}
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}