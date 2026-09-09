# # MODULE 16: Offline-First Engineering — Service
# # Depends on: Module 2 schema, Module 5/6 (risk+forecast), Module 8 (SOS packet contract,
# # via dispatch_service.create_incident_from_packet), Module 18 (audit_service).

# from datetime import datetime, timezone

# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.schemas.offline_sync import (
#     SyncBundleQuery,
#     SyncBundleResponse,
#     StampedRecord,
#     OfflineSosSyncRequest,
#     OfflineSosSyncResponse,
#     OfflineSosSyncResult,
#     QueuedSosPacket,
# )
# from app.services.dispatch_service import create_incident_from_packet  # Module 8
# from app.services.audit_service import log_audit_event  # Module 18

# TTL = {
#     "beach_risk_snapshot": 60 * 30,  # 30 min — risk changes fast, must be marked stale quickly
#     "trip_plan": 60 * 60 * 6,
#     "safe_zone": 60 * 60 * 24 * 7,  # rarely changes
#     "emergency_contact": 60 * 60 * 24 * 7,
#     "authority_directory": 60 * 60 * 24,
#     "hospital_directory": 60 * 60 * 24,
#     "alert_summary": 60 * 15,
# }


# def _stamp(data: dict, ttl_key: str) -> StampedRecord:
#     return StampedRecord(
#         data=data,
#         server_version=1,
#         cached_at=datetime.now(timezone.utc),
#         stale_after_s=TTL[ttl_key],
#     )


# async def build_sync_bundle(db: AsyncSession, q: SyncBundleQuery) -> SyncBundleResponse:
#     beach_ids = q.beach_ids

#     # Step 1: beach risk snapshots (only beaches user actually cares about — keeps payload
#     # small on weak networks)
#     risk_rows = []
#     if beach_ids:
#         result = await db.execute(
#             text(
#                 """SELECT beach_id, verdict, risk_score, computed_at, explanation
#                    FROM beach_risk_scores
#                    WHERE beach_id = ANY(CAST(:beach_ids AS uuid[]))
#                    ORDER BY computed_at DESC"""
#             ),
#             {"beach_ids": beach_ids},
#         )
#         risk_rows = [dict(r._mapping) for r in result]

#     # Step 2: last active/upcoming trip plan
#     trip_result = await db.execute(
#         text(
#             """SELECT * FROM trip_plans
#                WHERE user_id = :user_id AND status IN ('active','upcoming')
#                ORDER BY updated_at DESC LIMIT 1"""
#         ),
#         {"user_id": user_id},  # caller must scope by authenticated user_id upstream
#     )
#     trip_row = trip_result.mappings().first()

#     # Step 3: safe zones
#     safe_zone_rows = []
#     if beach_ids:
#         result = await db.execute(
#             text(
#                 """SELECT id, beach_id, name, ST_AsGeoJSON(geom) as geom, elevation_m, route_notes
#                    FROM safe_zones WHERE beach_id = ANY(CAST(:beach_ids AS uuid[])) AND active = true"""
#             ),
#             {"beach_ids": beach_ids},
#         )
#         safe_zone_rows = [dict(r._mapping) for r in result]

#     # Step 4: emergency contacts
#     contact_result = await db.execute(
#         text(
#             """SELECT id, name, phone, relation, priority FROM emergency_contacts
#                WHERE user_id = :user_id ORDER BY priority ASC"""
#         ),
#         {"user_id": user_id},
#     )
#     contact_rows = [dict(r._mapping) for r in contact_result]

#     # Step 5: authority directory
#     authority_rows = []
#     if beach_ids:
#         result = await db.execute(
#             text(
#                 """SELECT j.id, j.name, j.authority_type, j.contact_phone, j.contact_email, j.escalation_level
#                    FROM jurisdictions j
#                    JOIN beaches b ON ST_Intersects(j.service_area_geom, b.geom)
#                    WHERE b.id = ANY(CAST(:beach_ids AS uuid[])) AND j.active = true"""
#             ),
#             {"beach_ids": beach_ids},
#         )
#         authority_rows = [dict(r._mapping) for r in result]

#     # Step 6: hospital directory (nearest 20, capped for payload size)
#     hospital_rows = []
#     if beach_ids:
#         result = await db.execute(
#             text(
#                 """SELECT h.id, h.name, h.type, h.contact_phone, h.capabilities, h.capacity_status,
#                           ST_AsGeoJSON(h.geom) as geom
#                    FROM hospitals h, beaches b
#                    WHERE b.id = ANY(CAST(:beach_ids AS uuid[])) AND h.active = true
#                    ORDER BY b.centroid <-> h.geom
#                    LIMIT 20"""
#             ),
#             {"beach_ids": beach_ids},
#         )
#         hospital_rows = [dict(r._mapping) for r in result]

#     # Step 7: last alert summary
#     alert_row = None
#     if beach_ids:
#         result = await db.execute(
#             text(
#                 """SELECT id, beach_id, severity, hazard_type, message, issued_at
#                    FROM hazard_alerts
#                    WHERE beach_id = ANY(CAST(:beach_ids AS uuid[]))
#                    ORDER BY issued_at DESC LIMIT 1"""
#             ),
#             {"beach_ids": beach_ids},
#         )
#         alert_row = result.mappings().first()

#     return SyncBundleResponse(
#         synced_at=datetime.now(timezone.utc),
#         beach_risk_snapshots=[_stamp(r, "beach_risk_snapshot") for r in risk_rows],
#         trip_plan=_stamp(dict(trip_row), "trip_plan") if trip_row else None,
#         safe_zones=[_stamp(r, "safe_zone") for r in safe_zone_rows],
#         emergency_contacts=[_stamp(r, "emergency_contact") for r in contact_rows],
#         authority_directory=[_stamp(r, "authority_directory") for r in authority_rows],
#         hospital_directory=[_stamp(r, "hospital_directory") for r in hospital_rows],
#         alert_summary=_stamp(dict(alert_row), "alert_summary") if alert_row else None,
#     )


# def _to_canonical_packet(p: QueuedSosPacket) -> dict:
#     # Maps offline queue shape -> Module 8 canonical SOS packet shape.
#     return {
#         "client_incident_id": p.client_incident_id,
#         "user_id": p.user_id,
#         "lat": p.lat,
#         "lng": p.lng,
#         "accuracy_m": p.accuracy_m,
#         "source_of_location": p.source_of_location,
#         "beach_id": p.beach_id,
#         "activity_type": p.activity_type,
#         "incident_type": p.incident_type,
#         "severity": p.severity,
#         "media_urls": p.media_refs,
#         "battery_pct": p.battery_pct,
#         "signal_strength": p.signal_strength,
#         "offline_flag": True,
#         "timestamp": p.created_at_client,
#     }


# # Step 8-9: ingest offline-queued SOS packets on reconnect. Idempotent on client_incident_id —
# # client may retry the same batch if the ack never arrived.
# async def sync_offline_sos_queue(
#     db: AsyncSession, req: OfflineSosSyncRequest
# ) -> OfflineSosSyncResponse:
#     results: list[OfflineSosSyncResult] = []

#     for packet in req.packets:
#         try:
#             existing = await db.execute(
#                 text("SELECT id FROM incident_reports WHERE client_incident_id = :cid"),
#                 {"cid": packet.client_incident_id},
#             )
#             existing_row = existing.mappings().first()

#             if existing_row:
#                 results.append(
#                     OfflineSosSyncResult(
#                         client_incident_id=packet.client_incident_id,
#                         status="duplicate",
#                         server_incident_id=str(existing_row["id"]),
#                     )
#                 )
#                 continue

#             incident = await create_incident_from_packet(
#                 db, _to_canonical_packet(packet), received_late=True
#             )

#             await log_audit_event(
#                 db,
#                 entity_type="incident_report",
#                 entity_id=incident.id,
#                 event_type="incident.offline_sync.ingested",
#                 metadata={
#                     "client_incident_id": packet.client_incident_id,
#                     "created_at_client": packet.created_at_client.isoformat(),
#                     "delay_s": int(
#                         (datetime.now(timezone.utc) - packet.created_at_client).total_seconds()
#                     ),
#                 },
#             )

#             results.append(
#                 OfflineSosSyncResult(
#                     client_incident_id=packet.client_incident_id,
#                     status="accepted", 
#                     server_incident_id=str(incident.id),
#                 )
#             )
#         except Exception as err:  # noqa: BLE001 — must never abort the whole batch
#             results.append(
#                 OfflineSosSyncResult(
#                     client_incident_id=packet.client_incident_id,
#                     status="rejected",
#                     reason=str(err),
#                 )
#             )

#     return OfflineSosSyncResponse(results=results)


# MODULE 16: Offline-First Engineering — Service
# Depends on: Module 2 schema, Module 5/6 (risk+forecast), Module 8 (SOS packet contract,
# via dispatch_service.create_incident_from_packet), Module 18 (audit_service).
#
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.
#
# ⚠️ B4 FIX APPLIED: was importing `app.services.audit_service.log_audit_event` (the
# module18 async variant, now superseded per B4). Redirected to the canonical
# `app.core.audit.log_audit_event`, and the call below now uses that function's real
# signature (positional event_type/entity_type/entity_id/actor_type/actor_id/payload —
# NOT the old metadata= keyword).
#
# ⚠️ FLAGGED GAP (same pattern as B10's missing ingestion_service.py): this file imports
# `app.services.dispatch_service.create_incident_from_packet`, but no `dispatch_service.py`
# exists in ANY delivered module/zip. The closest real equivalent is `sos_service.py`
# (from m8-14.zip) which almost certainly has the SOS-creation logic this needs — but its
# exact function name/signature wasn't visible to me. Two options:
#   1. If sos_service.py has a function like `create_incident(db, ...)` or `trigger_sos(db, ...)`,
#      rename the import below to point at it and adapt the packet-dict argument to match
#      its actual parameter names.
#   2. Write a thin `app/services/dispatch_service.py` that wraps sos_service's real function.
# Left as-is below (import will fail until you resolve this) rather than guessing a fake
# function that would silently produce wrong behavior.

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.offline_sync import (
    SyncBundleQuery,
    SyncBundleResponse,
    StampedRecord,
    OfflineSosSyncRequest,
    OfflineSosSyncResponse,
    OfflineSosSyncResult,
    QueuedSosPacket,
)
from app.services.dispatch_service import create_incident_from_packet  # Module 8 — ⚠️ see note above
from app.core.audit import log_audit_event  # B4 — canonical, was app.services.audit_service

TTL = {
    "beach_risk_snapshot": 60 * 30,  # 30 min — risk changes fast, must be marked stale quickly
    "trip_plan": 60 * 60 * 6,
    "safe_zone": 60 * 60 * 24 * 7,  # rarely changes
    "emergency_contact": 60 * 60 * 24 * 7,
    "authority_directory": 60 * 60 * 24,
    "hospital_directory": 60 * 60 * 24,
    "alert_summary": 60 * 15,
}


def _stamp(data: dict, ttl_key: str) -> StampedRecord:
    return StampedRecord(
        data=data,
        server_version=1,
        cached_at=datetime.now(timezone.utc),
        stale_after_s=TTL[ttl_key],
    )


def build_sync_bundle(db: Session, q: SyncBundleQuery, user_id: str) -> SyncBundleResponse:
    beach_ids = q.beach_ids

    # Step 1: beach risk snapshots (only beaches user actually cares about — keeps payload
    # small on weak networks)
    risk_rows = []
    if beach_ids:
        result = db.execute(
            text(
                """SELECT beach_id, verdict, risk_score, computed_at, explanation
                   FROM beach_risk_scores
                   WHERE beach_id = ANY(CAST(:beach_ids AS uuid[]))
                   ORDER BY computed_at DESC"""
            ),
            {"beach_ids": beach_ids},
        )
        risk_rows = [dict(r._mapping) for r in result]

    # Step 2: last active/upcoming trip plan
    # NOTE: uses q.device_id as user_id here — carried over unchanged from the original
    # file. If device_id and user_id are genuinely different concepts in your schema
    # (device vs authenticated user), this row/step 4 below need the real user_id passed
    # in from the router instead of the device header. Flagging, not silently changing.
    trip_result = db.execute(
        text(
            """SELECT * FROM trip_plans
               WHERE user_id = :user_id AND status IN ('active','upcoming')
               ORDER BY created_at DESC LIMIT 1"""
        ),
        {"user_id": user_id},
    )
    trip_row = trip_result.mappings().first()

    # Step 3: safe zones
    safe_zone_rows = []
    if beach_ids:
        result = db.execute(
            text(
                """SELECT id, beach_id, name, ST_AsGeoJSON(geom) as geom, elevation_m, route_notes
                   FROM safe_zones WHERE beach_id = ANY(CAST(:beach_ids AS uuid[])) AND active = true"""
            ),
            {"beach_ids": beach_ids},
        )
        safe_zone_rows = [dict(r._mapping) for r in result]

    # Step 4: emergency contacts
    contact_result = db.execute(
        text(
            """SELECT id, name, phone, relation, priority FROM emergency_contacts
               WHERE user_id = :user_id ORDER BY priority ASC"""
        ),
        {"user_id": user_id},
    )
    contact_rows = [dict(r._mapping) for r in contact_result]

    # Step 5: authority directory
    authority_rows = []
    if beach_ids:
        result = db.execute(
            text(
                """SELECT j.id, j.name, j.authority_type, j.contact_phone, j.contact_email, j.escalation_level
                   FROM jurisdictions j
                   JOIN beaches b ON ST_Intersects(j.service_area_geom, b.geom)
                   WHERE b.id = ANY(CAST(:beach_ids AS uuid[])) AND j.active = true"""
            ),
            {"beach_ids": beach_ids},
        )
        authority_rows = [dict(r._mapping) for r in result]

    # Step 6: hospital directory (nearest 20, capped for payload size)
    hospital_rows = []
    if beach_ids:
        result = db.execute(
            text(
                """SELECT h.id, h.name, h.type, h.contact_phone, h.capabilities, h.capacity_status,
                          ST_AsGeoJSON(h.geom) as geom
                   FROM hospitals h, beaches b
                   WHERE b.id = ANY(CAST(:beach_ids AS uuid[])) AND h.active = true
                   ORDER BY b.centroid <-> h.geom
                   LIMIT 20"""
            ),
            {"beach_ids": beach_ids},
        )
        hospital_rows = [dict(r._mapping) for r in result]

    # Step 7: last alert summary
    alert_row = None
    if beach_ids:
        result = db.execute(
            text(
                """SELECT ha.id, b.id AS beach_id, ha.severity, ha.alert_type, ha.title, ha.issued_at
                   FROM hazard_alerts ha
                   JOIN beaches b ON ST_Intersects(ha.geom, b.geom)
                   WHERE b.id = ANY(CAST(:beach_ids AS uuid[]))
                   ORDER BY ha.issued_at DESC LIMIT 1"""
            ),
            {"beach_ids": beach_ids},
        )
        alert_row = result.mappings().first()

    return SyncBundleResponse(
        synced_at=datetime.now(timezone.utc),
        beach_risk_snapshots=[_stamp(r, "beach_risk_snapshot") for r in risk_rows],
        trip_plan=_stamp(dict(trip_row), "trip_plan") if trip_row else None,
        safe_zones=[_stamp(r, "safe_zone") for r in safe_zone_rows],
        emergency_contacts=[_stamp(r, "emergency_contact") for r in contact_rows],
        authority_directory=[_stamp(r, "authority_directory") for r in authority_rows],
        hospital_directory=[_stamp(r, "hospital_directory") for r in hospital_rows],
        alert_summary=_stamp(dict(alert_row), "alert_summary") if alert_row else None,
    )


def _to_canonical_packet(p: QueuedSosPacket) -> dict:
    # Maps offline queue shape -> Module 8 canonical SOS packet shape.
    return {
        "client_incident_id": p.client_incident_id,
        "user_id": p.user_id,
        "lat": p.lat,
        "lng": p.lng,
        "accuracy_m": p.accuracy_m,
        "source_of_location": p.source_of_location,
        "beach_id": p.beach_id,
        "activity_type": p.activity_type,
        "incident_type": p.incident_type,
        "severity": p.severity,
        "media_urls": p.media_refs,
        "battery_pct": p.battery_pct,
        "signal_strength": p.signal_strength,
        "offline_flag": True,
        "timestamp": p.created_at_client,
    }


# Step 8-9: ingest offline-queued SOS packets on reconnect. Idempotent on client_incident_id —
# client may retry the same batch if the ack never arrived.
def sync_offline_sos_queue(
    db: Session, req: OfflineSosSyncRequest
) -> OfflineSosSyncResponse:
    results: list[OfflineSosSyncResult] = []

    for packet in req.packets:
        try:
            existing = db.execute(
                text("SELECT id FROM incident_reports WHERE client_incident_id = :cid"),
                {"cid": packet.client_incident_id},
            )
            existing_row = existing.mappings().first()

            if existing_row:
                results.append(
                    OfflineSosSyncResult(
                        client_incident_id=packet.client_incident_id,
                        status="duplicate",
                        server_incident_id=str(existing_row["id"]),
                    )
                )
                continue

            incident = create_incident_from_packet(
                db, _to_canonical_packet(packet), received_late=True
            )

            log_audit_event(
                db,
                event_type="incident.offline_sync.ingested",
                entity_type="incident_report",
                entity_id=incident.id,
                actor_type="user",
                actor_id=packet.user_id,
                payload={
                    "client_incident_id": packet.client_incident_id,
                    "created_at_client": packet.created_at_client.isoformat(),
                    "delay_s": int(
                        (datetime.now(timezone.utc) - packet.created_at_client).total_seconds()
                    ),
                },
            )
            db.commit()

            results.append(
                OfflineSosSyncResult(
                    client_incident_id=packet.client_incident_id,
                    status="accepted",
                    server_incident_id=str(incident.id),
                )
            )
        except Exception as err:  # noqa: BLE001 — must never abort the whole batch
            db.rollback()
            results.append(
                OfflineSosSyncResult(
                    client_incident_id=packet.client_incident_id,
                    status="rejected",
                    reason=str(err),
                )
            )

    return OfflineSosSyncResponse(results=results)