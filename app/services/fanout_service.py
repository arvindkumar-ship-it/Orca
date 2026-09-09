# """
# Module 14 — Emergency Contact Fanout.
# Reuses Module 22's tables: emergency_share_sessions, emergency_share_targets.
# Notification calls use the canonical enqueue() contract (Module 13 rewrite).
# """
# from sqlalchemy import text
# from sqlalchemy.orm import Session

# from app.core.config import settings
# from app.core.audit import log_audit_event
# from app.services.notification_service import enqueue


# def _build_share_card(db: Session, incident_report_id) -> dict:
#     ir = db.execute(text("SELECT incident_type, status FROM incident_reports WHERE id = :id"),
#                      {"id": incident_report_id}).mappings().first()
#     if not ir:
#         raise ValueError("INCIDENT_NOT_FOUND")

#     ping = db.execute(text("""
#         SELECT ST_X(lp.geom) AS lng, ST_Y(lp.geom) AS lat, lp.created_at
#         FROM location_pings lp JOIN live_tracking_sessions lts ON lts.id = lp.session_id
#         WHERE lts.incident_report_id = :id ORDER BY lp.created_at DESC LIMIT 1
#     """), {"id": incident_report_id}).mappings().first()

#     sz = db.execute(text("""SELECT instruction_text FROM safezone_guidance
#                              WHERE incident_report_id = :id AND superseded = false
#                              ORDER BY computed_at DESC LIMIT 1"""), {"id": incident_report_id}).mappings().first()
#     ack = db.execute(text("""SELECT ack_status FROM incident_routes WHERE incident_report_id = :id
#                               AND target_type = 'authority' ORDER BY ack_time DESC NULLS LAST, routed_at DESC LIMIT 1"""),
#                       {"id": incident_report_id}).mappings().first()

#     return {
#         "last_location": {"lat": float(ping["lat"]), "lng": float(ping["lng"]), "as_of": ping["created_at"].isoformat()} if ping else None,
#         "live_map_link": f"{settings.APP_BASE_URL}/track/{incident_report_id}",
#         "incident_type": ir["incident_type"], "status": ir["status"],
#         "safety_instruction": sz["instruction_text"] if sz else None,
#         "authority_ack_status": ack["ack_status"] if ack else "pending",
#     }


# def start_fanout(db: Session, incident_report_id: str, user_id: str, share_with: list[str] | None,
#                   share_live_location: bool, share_route: bool) -> dict:
#     existing = db.execute(text("""SELECT id FROM emergency_share_sessions
#                                    WHERE incident_report_id = :id AND status = 'active'"""),
#                            {"id": incident_report_id}).mappings().first()
#     if existing:
#         return send_update(db, str(existing["id"]))

#     row = db.execute(text("""
#         INSERT INTO emergency_share_sessions (incident_report_id, share_live_location, share_route)
#         VALUES (:irid,:sll,:sr) RETURNING id
#     """), {"irid": incident_report_id, "sll": share_live_location, "sr": share_route}).mappings().first()
#     session_id = str(row["id"])

#     contacts = db.execute(text(
#         """SELECT id, name, phone FROM emergency_contacts WHERE user_id = :uid AND id = ANY(:ids)""" if share_with
#         else """SELECT id, name, phone FROM emergency_contacts WHERE user_id = :uid ORDER BY priority ASC"""
#     ), {"uid": user_id, **({"ids": share_with} if share_with else {})}).mappings().all()

#     card = _build_share_card(db, incident_report_id)
#     recipients = []
#     for c in contacts:
#         db.execute(text("""INSERT INTO emergency_share_targets (share_session_id, contact_id, status, last_update_sent_at)
#                             VALUES (:sid,:cid,'sent', now())"""), {"sid": session_id, "cid": c["id"]})
#         enqueue(db, incident_report_id=incident_report_id, user_id=user_id, type="contact_fanout_start",
#                 priority="critical", template_key="contact_fanout_start", vars={
#                     "contact_name": c["name"], "incident_type": card["incident_type"],
#                     "map_link": card["live_map_link"], "instruction": card["safety_instruction"] or "Rescue in progress.",
#                 })
#         recipients.append({"contact_id": str(c["id"]), "status": "sent"})
#     db.commit()

#     log_audit_event(db, event_type="fanout.session.started", entity_type="emergency_share_session",
#                      entity_id=session_id, actor_type="user", actor_id=user_id, payload={"recipient_count": len(contacts)})
#     return {"session_id": session_id, "recipients": recipients}


# def send_update(db: Session, session_id: str) -> dict:
#     sess = db.execute(text("SELECT incident_report_id, user_id, status FROM emergency_share_sessions WHERE id = :id"),
#                        {"id": session_id}).mappings().first()
#     if not sess:
#         raise ValueError("SESSION_NOT_FOUND")
#     if sess["status"] != "active":
#         raise ValueError("SESSION_NOT_ACTIVE")

#     card = _build_share_card(db, sess["incident_report_id"])
#     recipients = db.execute(text("""
#         SELECT est.id, est.contact_id, ec.name FROM emergency_share_targets est
#         JOIN emergency_contacts ec ON ec.id = est.contact_id WHERE est.share_session_id = :sid
#     """), {"sid": session_id}).mappings().all()

#     for r in recipients:
#         enqueue(db, incident_report_id=sess["incident_report_id"], user_id=sess["user_id"],
#                 type="contact_fanout_update", priority="high", template_key="contact_fanout_update", vars={
#                     "contact_name": r["name"], "status": card["status"],
#                     "map_link": card["live_map_link"], "ack": card["authority_ack_status"],
#                 })
#         db.execute(text("UPDATE emergency_share_targets SET last_update_sent_at = now() WHERE id = :id"), {"id": r["id"]})
#     db.commit()

#     return {"session_id": session_id, "recipients": [{"contact_id": str(r["contact_id"]), "status": "sent"} for r in recipients]}


# def stop_fanout(db: Session, session_id: str, reason: str, actor_id: str | None) -> None:
#     res = db.execute(text("""
#         UPDATE emergency_share_sessions SET status = 'stopped', stopped_at = now(), stop_reason = :r
#         WHERE id = :id AND status = 'active' RETURNING id, user_id, incident_report_id
#     """), {"r": reason, "id": session_id})
#     row = res.mappings().first()
#     if not row:
#         raise ValueError("SESSION_NOT_FOUND_OR_ALREADY_STOPPED")

#     enqueue(db, incident_report_id=row["incident_report_id"], user_id=row["user_id"],
#             type="contact_fanout_stop", priority="normal", template_key="contact_fanout_stop", vars={"reason": reason})
#     db.commit()

#     log_audit_event(db, event_type="fanout.session.stopped", entity_type="emergency_share_session", entity_id=session_id,
#                      actor_type="user" if actor_id else "system", actor_id=actor_id, payload={"reason": reason})


# def on_incident_updated(db: Session, incident_report_id: str) -> None:
#     rows = db.execute(text("SELECT id FROM emergency_share_sessions WHERE incident_report_id = :id AND status = 'active'"),
#                        {"id": incident_report_id}).mappings().all()
#     for r in rows:
#         send_update(db, str(r["id"]))


# def on_incident_closed(db: Session, incident_report_id: str) -> None:
#     rows = db.execute(text("SELECT id FROM emergency_share_sessions WHERE incident_report_id = :id AND status = 'active'"),
#                        {"id": incident_report_id}).mappings().all()
#     for r in rows:
#         stop_fanout(db, str(r["id"]), "resolved", None)







"""
Module 14 — Emergency Contact Fanout.
Reuses Module 22's tables: emergency_share_sessions, emergency_share_targets
(schema exactly as created in migrations/016b_safezone_emergency_share_tables.sql —
no stop_reason, no last_update_sent_at, no session.user_id columns exist).

FIX (2026-08-22): emergency_contacts are name+phone rows, not app accounts — they
have no users.id and no device. app.services.notification_service.enqueue() only
delivers through NotificationQueue.user_id (a users.id FK: push via user_devices,
SMS via users.phone — see notification_service.deliver()). Routing contact fanout
through enqueue(user_id=<incident owner>) delivered every "contact notified"
message back to the incident owner's own phone/device and never reached the
emergency contact at all. Fixed to SMS each contact directly on their own
emergency_contacts.phone via the existing send_sms() channel (same channel
already used for authority/hospital dispatch in authority_router_service.py /
hospital_router_service.py).
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.audit import log_audit_event
from app.services.channels.sms_channel import send_sms


def _build_share_card(db: Session, incident_report_id) -> dict:
    ir = db.execute(text("SELECT incident_type, status FROM incident_reports WHERE id = :id"),
                     {"id": incident_report_id}).mappings().first()
    if not ir:
        raise ValueError("INCIDENT_NOT_FOUND")

    ping = db.execute(text("""
        SELECT ST_X(lp.geom) AS lng, ST_Y(lp.geom) AS lat, lp.created_at
        FROM location_pings lp JOIN live_tracking_sessions lts ON lts.id = lp.session_id
        WHERE lts.incident_report_id = :id ORDER BY lp.created_at DESC LIMIT 1
    """), {"id": incident_report_id}).mappings().first()

    sz = db.execute(text("""SELECT instruction_text FROM safezone_guidance
                             WHERE incident_report_id = :id AND superseded = false
                             ORDER BY computed_at DESC LIMIT 1"""), {"id": incident_report_id}).mappings().first()
    ack = db.execute(text("""SELECT ack_status FROM incident_routes WHERE incident_report_id = :id
                              AND target_type = 'authority' ORDER BY ack_time DESC NULLS LAST, routed_at DESC LIMIT 1"""),
                      {"id": incident_report_id}).mappings().first()

    return {
        "last_location": {"lat": float(ping["lat"]), "lng": float(ping["lng"]), "as_of": ping["created_at"].isoformat()} if ping else None,
        "live_map_link": f"{settings.APP_BASE_URL}/track/{incident_report_id}",
        "incident_type": ir["incident_type"], "status": ir["status"],
        "safety_instruction": sz["instruction_text"] if sz else None,
        "authority_ack_status": ack["ack_status"] if ack else "pending",
    }


def _share_sms_text(card: dict, contact_name: str, prefix: str) -> str:
    loc = "location unavailable"
    if card["last_location"]:
        loc = f"https://maps.google.com/?q={card['last_location']['lat']},{card['last_location']['lng']}"
    instruction = card["safety_instruction"] or "Rescue in progress."
    return (f"WaveSafe {prefix} for {contact_name}: {card['incident_type']} incident, "
            f"status {card['status']}. Last known location: {loc}. Track live: {card['live_map_link']}. "
            f"{instruction}")


def start_fanout(db: Session, incident_report_id: str, user_id: str, share_with: list[str] | None,
                  share_live_location: bool, share_route: bool) -> dict:
    existing = db.execute(text("""SELECT id FROM emergency_share_sessions
                                   WHERE incident_report_id = :id AND status = 'active'"""),
                           {"id": incident_report_id}).mappings().first()
    if existing:
        return send_update(db, str(existing["id"]))

    row = db.execute(text("""
        INSERT INTO emergency_share_sessions (incident_report_id, share_live_location, share_route)
        VALUES (:irid,:sll,:sr) RETURNING id
    """), {"irid": incident_report_id, "sll": share_live_location, "sr": share_route}).mappings().first()
    session_id = str(row["id"])

    contacts = db.execute(text(
        """SELECT id, name, phone FROM emergency_contacts WHERE user_id = :uid AND id = ANY(:ids)""" if share_with
        else """SELECT id, name, phone FROM emergency_contacts WHERE user_id = :uid ORDER BY priority ASC"""
    ), {"uid": user_id, **({"ids": share_with} if share_with else {})}).mappings().all()

    card = _build_share_card(db, incident_report_id)
    recipients = []
    for c in contacts:
        sms_result = send_sms(c["phone"], _share_sms_text(card, c["name"], "Alert"))
        target_status = "sent" if sms_result["ok"] else "failed"
        db.execute(text("""INSERT INTO emergency_share_targets (share_session_id, contact_id, status, last_error)
                            VALUES (:sid,:cid,:st,:err)"""),
                   {"sid": session_id, "cid": c["id"], "st": target_status, "err": sms_result.get("error")})
        recipients.append({"contact_id": str(c["id"]), "status": target_status})
    db.commit()

    log_audit_event(db, event_type="fanout.session.started", entity_type="emergency_share_session",
                     entity_id=session_id, actor_type="user", actor_id=user_id,
                     payload={"recipient_count": len(contacts),
                               "sent_count": sum(1 for r in recipients if r["status"] == "sent")})
    return {"session_id": session_id, "recipients": recipients}


def send_update(db: Session, session_id: str) -> dict:
    sess = db.execute(text("SELECT incident_report_id, status FROM emergency_share_sessions WHERE id = :id"),
                       {"id": session_id}).mappings().first()
    if not sess:
        raise ValueError("SESSION_NOT_FOUND")
    if sess["status"] != "active":
        raise ValueError("SESSION_NOT_ACTIVE")

    card = _build_share_card(db, sess["incident_report_id"])
    recipients = db.execute(text("""
        SELECT est.id, est.contact_id, ec.name, ec.phone FROM emergency_share_targets est
        JOIN emergency_contacts ec ON ec.id = est.contact_id WHERE est.share_session_id = :sid
    """), {"sid": session_id}).mappings().all()

    results = []
    for r in recipients:
        sms_result = send_sms(r["phone"], _share_sms_text(card, r["name"], "Update"))
        target_status = "sent" if sms_result["ok"] else "failed"
        db.execute(text("UPDATE emergency_share_targets SET status = :st, last_error = :err WHERE id = :id"),
                   {"st": target_status, "err": sms_result.get("error"), "id": r["id"]})
        results.append({"contact_id": str(r["contact_id"]), "status": target_status})
    db.commit()

    return {"session_id": session_id, "recipients": results}


def stop_fanout(db: Session, session_id: str, reason: str, actor_id: str | None) -> None:
    res = db.execute(text("""
        UPDATE emergency_share_sessions SET status = 'stopped', stopped_at = now()
        WHERE id = :id AND status = 'active' RETURNING id, incident_report_id
    """), {"id": session_id})
    row = res.mappings().first()
    if not row:
        raise ValueError("SESSION_NOT_FOUND_OR_ALREADY_STOPPED")

    recipients = db.execute(text("""
        SELECT ec.name, ec.phone FROM emergency_share_targets est
        JOIN emergency_contacts ec ON ec.id = est.contact_id
        WHERE est.share_session_id = :sid AND est.status = 'sent'
    """), {"sid": session_id}).mappings().all()

    stop_text = f"WaveSafe Alert: location sharing has stopped ({reason})."
    for r in recipients:
        send_sms(r["phone"], stop_text)
    db.commit()

    log_audit_event(db, event_type="fanout.session.stopped", entity_type="emergency_share_session", entity_id=session_id,
                     actor_type="user" if actor_id else "system", actor_id=actor_id, payload={"reason": reason})


def on_incident_updated(db: Session, incident_report_id: str) -> None:
    rows = db.execute(text("SELECT id FROM emergency_share_sessions WHERE incident_report_id = :id AND status = 'active'"),
                       {"id": incident_report_id}).mappings().all()
    for r in rows:
        send_update(db, str(r["id"]))


def on_incident_closed(db: Session, incident_report_id: str) -> None:
    rows = db.execute(text("SELECT id FROM emergency_share_sessions WHERE incident_report_id = :id AND status = 'active'"),
                       {"id": incident_report_id}).mappings().all()
    for r in rows:
        stop_fanout(db, str(r["id"]), "resolved", None)