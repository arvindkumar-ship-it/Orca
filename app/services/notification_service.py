"""
Module 13 — Notification Service. Canonical contract, matching real callers found in the
codebase during the Module 8/9/10/14/27 consistency check:
- enqueue(...)  <- called by dispatch_state_machine.py (title/body already built) AND by
                    fanout_service/sos_service etc. (template_key + vars)
- deliver(db, notification) -> bool  <- called by notification_worker.flush_notification_queue
"""
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.incident import NotificationQueue
from app.services.notification_templates import render_template
from app.services.channels.push_channel import send_push
from app.services.channels.sms_channel import send_sms

# Tiers that require SMS as well as push (mirrors Module 27's priority mapping: critical/high -> both)
SMS_PRIORITIES = {"critical", "high"}
FULL_SCREEN_PRIORITIES = {"critical"}


def enqueue(
    db: Session,
    *,
    incident_report_id=None,
    user_id=None,
    type: str,
    priority: str = "normal",
    title: str | None = None,
    body: str | None = None,
    template_key: str | None = None,
    vars: dict | None = None,
    locale: str = "en",
) -> NotificationQueue:
    if template_key:
        rendered = render_template(db, template_key, locale, vars or {})
        title, body = rendered["title"], rendered["body"]
    if title is None or body is None:
        raise ValueError("enqueue() requires either title+body or template_key")

    # If caller didn't pass user_id (Module 27's state-machine calls don't), resolve from the incident.
    if user_id is None and incident_report_id is not None:
        row = db.execute(
            text("SELECT user_id FROM incident_reports WHERE id = :id"),
            {"id": str(incident_report_id)},
        ).mappings().first()
        user_id = row["user_id"] if row else None

    n = NotificationQueue(
        user_id=user_id, incident_report_id=incident_report_id, type=type, priority=priority,
        title=title, body=body, channel="push", status="queued",
        full_screen=priority in FULL_SCREEN_PRIORITIES, locale=locale, delivery_meta={},
    )
    db.add(n)
    db.flush()
    return n


def deliver(db: Session, notification: NotificationQueue) -> bool:
    """Called by notification_worker per-row. Returns True only if EVERY required channel succeeded."""
    ok = True

    push_result = send_push(db, str(notification.user_id), notification.title, notification.body, notification.full_screen)
    if not push_result["ok"]:
        ok = False

    if notification.priority in SMS_PRIORITIES:
        phone_row = db.execute(
            text("SELECT phone FROM users WHERE id = :id"), {"id": str(notification.user_id)}
        ).mappings().first()
        sms_result = send_sms(phone_row["phone"] if phone_row else "", notification.body)
        if not sms_result["ok"]:
            ok = False

    return ok
