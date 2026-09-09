# """
# Module 22 service layer.
# Depends on:
# - app.models.contact.EmergencyContact (Module 2A: emergency_contacts)
# - app.services.notification_service.enqueue_notification(...) (Module 13)
# """
# import uuid
# from datetime import datetime, timezone

# from app.schemas import trip
# from sqlalchemy.orm import Session

# from app.core.exceptions import NotFoundError, ValidationError
# from app.models.incident import IncidentReport
# from app.models.core import EmergencyContact
# from app.models.emergency_share import EmergencyShareSession, EmergencyShareTarget, ShareStatus
# from app.services.notification_service import enqueue


# def start_share(db: Session, payload) -> EmergencyShareSession:
#     incident = db.query(IncidentReport).filter(IncidentReport.id == payload.incident_id).first()
#     if not incident:
#         raise NotFoundError("Incident not found")

#     contacts = (
#         db.query(EmergencyContact)
#         .filter(EmergencyContact.id.in_(payload.share_with), EmergencyContact.user_id == incident.user_id)
#         .all()
#     )
#     if not contacts:
#         raise ValidationError("No valid emergency contacts for this incident's user")

#     session = EmergencyShareSession(
#         incident_report_id=incident.id,
#         share_live_location=payload.share_live_location,
#         share_route=payload.share_route,
#         status=ShareStatus.ACTIVE,
#     )
#     db.add(session)
#     db.flush()

#     for contact in contacts:
#         target_status = "sent"
#         try:
#             enqueue(
#                 db,
#                 incident_report_id=incident.id,
#                 user_id=contact.user_id,
#                 type="emergency_share",
#                 priority="high",
#                 title="Emergency location share",
#                 body=f"{incident.incident_type} incident reported. Live location and route are being shared with you.",
#             )
#         except Exception:
#             target_status = "failed"
#         db.add(EmergencyShareTarget(share_session_id=session.id, contact_id=contact.id, status=target_status))

#     db.commit()
#     db.refresh(session)
#     return session


# def stop_share(db: Session, share_session_id: uuid.UUID) -> EmergencyShareSession:
#     session = db.query(EmergencyShareSession).filter(EmergencyShareSession.id == share_session_id).first()
#     if not session:
#         raise NotFoundError("Share session not found")
#     session.status = ShareStatus.STOPPED
#     session.stopped_at = datetime.now(timezone.utc)
#     db.commit()
#     db.refresh(session)
#     return session


# def get_share(db: Session, share_session_id: uuid.UUID) -> EmergencyShareSession:
#     session = db.query(EmergencyShareSession).filter(EmergencyShareSession.id == share_session_id).first()
#     if not session:
#         raise NotFoundError("Share session not found")
#     return session


"""
Module 22 service layer.
Depends on:
- app.models.contact.EmergencyContact (Module 2A: emergency_contacts)
- app.services.channels.sms_channel.send_sms (Module 13's push channel)

FIX (2026-08-22): EmergencyContact.user_id is the incident owner's id (whose
contact list this is) — it is NOT the contact's own account. Routing through
notification_service.enqueue(user_id=contact.user_id) delivered every share
notification back to the incident owner's own device/phone and never reached
the contact. Emergency contacts have no app account/device at all, only a
phone number — so delivery goes directly through send_sms() to
contact.phone, same channel already used for authority/hospital dispatch.
"""
import uuid
from datetime import datetime, timezone

from app.schemas import trip
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.incident import IncidentReport
from app.models.core import EmergencyContact
from app.models.emergency_share import EmergencyShareSession, EmergencyShareTarget, ShareStatus
from app.services.channels.sms_channel import send_sms


def start_share(db: Session, payload) -> EmergencyShareSession:
    incident = db.query(IncidentReport).filter(IncidentReport.id == payload.incident_id).first()
    if not incident:
        raise NotFoundError("Incident not found")

    contacts = (
        db.query(EmergencyContact)
        .filter(EmergencyContact.id.in_(payload.share_with), EmergencyContact.user_id == incident.user_id)
        .all()
    )
    if not contacts:
        raise ValidationError("No valid emergency contacts for this incident's user")

    session = EmergencyShareSession(
        incident_report_id=incident.id,
        share_live_location=payload.share_live_location,
        share_route=payload.share_route,
        status=ShareStatus.ACTIVE,
    )
    db.add(session)
    db.flush()

    message = (f"WaveSafe Alert: {incident.incident_type} incident reported. "
               f"Live location and route are being shared with you.")
    for contact in contacts:
        sms_result = send_sms(contact.phone, message)
        target_status = "sent" if sms_result["ok"] else "failed"
        db.add(EmergencyShareTarget(share_session_id=session.id, contact_id=contact.id,
                                     status=target_status, last_error=sms_result.get("error")))

    db.commit()
    db.refresh(session)
    return session


def stop_share(db: Session, share_session_id: uuid.UUID) -> EmergencyShareSession:
    session = db.query(EmergencyShareSession).filter(EmergencyShareSession.id == share_session_id).first()
    if not session:
        raise NotFoundError("Share session not found")
    session.status = ShareStatus.STOPPED
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def get_share(db: Session, share_session_id: uuid.UUID) -> EmergencyShareSession:
    session = db.query(EmergencyShareSession).filter(EmergencyShareSession.id == share_session_id).first()
    if not session:
        raise NotFoundError("Share session not found")
    return session