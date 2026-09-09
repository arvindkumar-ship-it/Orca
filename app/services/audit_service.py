# # MODULE 18: Audit and Analytics — Service
# # This is the assumed `audit` dependency referenced by every other module (Module 8
# # dispatch, Module 9/10 routers, Module 17 admin, Module 20-26 APIs). Single write
# # entrypoint for audit_events — never write to that table directly elsewhere.

# import json
# from typing import Any, Optional

# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.schemas.audit import (
#     MeanResponseTimeResult,
#     AlertAccuracyResult,
#     MissedWarningResult,
#     ThresholdRefitRecommendation,
# )


# # Step 1: store all events.
# async def log_audit_event(
#     db: AsyncSession,
#     *,
#     event_type: str,
#     entity_type: str,
#     entity_id: str,
#     actor_type: str = "system",
#     actor_id: Optional[str] = None,
#     metadata: Optional[dict[str, Any]] = None,
# ) -> None:
#     await db.execute(
#         text(
#             """INSERT INTO audit_events (event_type, entity_type, entity_id, actor_type, actor_id, payload)
#                VALUES (:event_type, :entity_type, :entity_id, :actor_type, :actor_id, :payload)"""
#         ),
#         {
#             "event_type": event_type,
#             "entity_type": entity_type,
#             "entity_id": entity_id,
#             "actor_type": actor_type,
#             "actor_id": actor_id,
#             "payload": json.dumps(metadata or {}, default=str),
#         },
#     )
#     await db.commit()


# # Step 2: store all changes (state transitions on incidents).
# async def log_status_change(
#     db: AsyncSession,
#     *,
#     incident_report_id: str,
#     from_status: Optional[str],
#     to_status: str,
#     reason: Optional[str] = None,
# ) -> None:
#     await db.execute(
#         text(
#             """INSERT INTO incident_status_history (incident_report_id, from_status, to_status, reason)
#                VALUES (:iid, :from_status, :to_status, :reason)"""
#         ),
#         {
#             "iid": incident_report_id,
#             "from_status": from_status,
#             "to_status": to_status,
#             "reason": reason,
#         },
#     )
#     await db.commit()
#     await log_audit_event(
#         db,
#         event_type="incident.status_changed",
#         entity_type="incident_report",
#         entity_id=incident_report_id,
#         metadata={"from": from_status, "to": to_status, "reason": reason},
#     )


# # Step 3: store all acknowledgements.
# async def log_acknowledgement(
#     db: AsyncSession, *, incident_route_id: str, ack_status: str, ack_time: str
# ) -> None:
#     await db.execute(
#         text(
#             "UPDATE incident_routes SET ack_status = :status, ack_time = :ack_time WHERE id = :id"
#         ),
#         {"status": ack_status, "ack_time": ack_time, "id": incident_route_id},
#     )
#     result = await db.execute(
#         text("SELECT incident_report_id, target_type FROM incident_routes WHERE id = :id"),
#         {"id": incident_route_id},
#     )
#     row = result.mappings().first()
#     await db.commit()
#     if row:
#         await log_audit_event(
#             db,
#             event_type="incident.ack_received",
#             entity_type="incident_route",
#             entity_id=incident_route_id,
#             metadata={
#                 "incident_report_id": row["incident_report_id"],
#                 "target_type": row["target_type"],
#                 "ack_status": ack_status,
#             },
#         )


# # Step 4: compute mean response time (dispatch -> ack, across all route targets).
# async def compute_mean_response_time(db: AsyncSession, window_days: int) -> MeanResponseTimeResult:
#     result = await db.execute(
#         text(
#             """SELECT EXTRACT(EPOCH FROM (ack_time - routed_at)) as response_s
#                FROM incident_routes
#                WHERE routed_at >= now() - (:days || ' days')::interval
#                  AND ack_time IS NOT NULL"""
#         ),
#         {"days": window_days},
#     )
#     values = [float(r["response_s"]) for r in result.mappings().all()]
#     mean = sum(values) / len(values) if values else 0.0
#     return MeanResponseTimeResult(window_days=window_days, mean_response_time_s=mean, sample_size=len(values))


# # Step 5 + 6: alert accuracy + false positive rate.
# # True positive: hazard_alert whose geom+validity window overlaps at least one
# # incident_report within that window. False positive: no matching incident.
# async def compute_alert_accuracy(db: AsyncSession, window_days: int) -> AlertAccuracyResult:
#     result = await db.execute(
#         text(
#             """SELECT
#                  ha.id,
#                  EXISTS (
#                    SELECT 1 FROM incident_reports ir
#                    WHERE ir.created_at BETWEEN ha.valid_from AND COALESCE(ha.valid_to, now())
#                      AND ST_Intersects(ir.geom, ha.geom)
#                  ) as matched_incident
#                FROM hazard_alerts ha
#                WHERE ha.issued_at >= now() - (:days || ' days')::interval"""
#         ),
#         {"days": window_days},
#     )
#     rows = result.mappings().all()
#     total = len(rows)
#     true_positive = sum(1 for r in rows if r["matched_incident"])
#     false_positive = total - true_positive

#     return AlertAccuracyResult(
#         window_days=window_days,
#         total_alerts=total,
#         true_positive_alerts=true_positive,
#         false_positive_alerts=false_positive,
#         accuracy=(true_positive / total) if total else 0.0,
#         false_positive_rate=(false_positive / total) if total else 0.0,
#     )


# # Step 7: missed warning rate — incident occurred with no active hazard_alert covering it.
# async def compute_missed_warning_rate(db: AsyncSession, window_days: int) -> MissedWarningResult:
#     result = await db.execute(
#         text(
#             """SELECT
#                  ir.id,
#                  EXISTS (
#                    SELECT 1 FROM hazard_alerts ha
#                    WHERE ir.created_at BETWEEN ha.valid_from AND COALESCE(ha.valid_to, now())
#                      AND ST_Intersects(ir.geom, ha.geom)
#                  ) as had_active_alert
#                FROM incident_reports ir
#                WHERE ir.created_at >= now() - (:days || ' days')::interval"""
#         ),
#         {"days": window_days},
#     )
#     rows = result.mappings().all()
#     total = len(rows)
#     missed = sum(1 for r in rows if not r["had_active_alert"])

#     return MissedWarningResult(
#         window_days=window_days,
#         total_incidents=total,
#         missed_incidents=missed,
#         missed_warning_rate=(missed / total) if total else 0.0,
#     )


# # Step 8: refit thresholds manually after review. Does NOT auto-apply — only computes
# # and records a recommendation for human review (Module 17 enforces admin-only manual
# # application via risk-rule tuning).
# async def generate_threshold_refit_recommendations(
#     db: AsyncSession, window_days: int
# ) -> list[ThresholdRefitRecommendation]:
#     result = await db.execute(
#         text(
#             """SELECT
#                  ir.beach_id,
#                  bap.activity_type,
#                  bap.min_safe_wave_height,
#                  count(*) as incident_count,
#                  avg((ir.current_hazard_context->>'wave_height_m')::numeric) as avg_wave_height_at_incident
#                FROM incident_reports ir
#                JOIN beach_activity_profiles bap ON bap.beach_id = ir.beach_id
#                WHERE ir.created_at >= now() - (:days || ' days')::interval
#                  AND ir.current_hazard_context ? 'wave_height_m'
#                GROUP BY ir.beach_id, bap.activity_type, bap.min_safe_wave_height
#                HAVING count(*) >= 3"""
#         ),
#         {"days": window_days},
#     )
#     rows = result.mappings().all()

#     recs = [
#         ThresholdRefitRecommendation(
#             beach_id=str(r["beach_id"]),
#             activity_type=r["activity_type"],
#             rule_parameter="min_safe_wave_height",
#             current_value=float(r["min_safe_wave_height"]) if r["min_safe_wave_height"] else None,
#             recommended_value=float(r["avg_wave_height_at_incident"]),
#             justification=(
#                 f"{r['incident_count']} incidents in last {window_days}d occurred at avg wave "
#                 f"height {float(r['avg_wave_height_at_incident']):.2f}m, below/near current "
#                 f"threshold — suggests threshold is too permissive."
#             ),
#             based_on_incident_count=int(r["incident_count"]),
#         )
#         for r in rows
#     ]

#     for rec in recs:
#         await log_audit_event(
#             db,
#             event_type="analytics.threshold_refit_recommended",
#             entity_type="beach_activity_profile",
#             entity_id=rec.beach_id,
#             metadata=rec.model_dump(),
#         )

#     return recs



# MODULE 18: Audit and Analytics — Service
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.
#
# ⚠️ B4 FIX APPLIED: this file used to define its OWN `log_audit_event`, duplicating the
# same `audit_events` insert that app.core.audit.log_audit_event now does canonically.
# Per B4 that duplication is removed here — `log_audit_event` is now just re-exported from
# app.core.audit (so any old `from app.services.audit_service import log_audit_event`
# call sites elsewhere in your codebase keep working without edits, but there is only ONE
# real implementation now, in app/core/audit.py).
#
# log_status_change() and log_acknowledgement() are kept — they're real business logic
# (writing to incident_status_history / incident_routes), not pure audit duplication —
# but their final audit-trail write now goes through the canonical function too.
#
# The analytics functions below (compute_mean_response_time, compute_alert_accuracy,
# compute_missed_warning_rate, generate_threshold_refit_recommendations) are genuinely
# this module's own logic and are unaffected by B4 — only converted to sync.

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import log_audit_event  # noqa: F401 — re-exported, see note above
from app.schemas.audit import (
    MeanResponseTimeResult,
    AlertAccuracyResult,
    MissedWarningResult,
    ThresholdRefitRecommendation,
)


# Step 2: store all changes (state transitions on incidents).
def log_status_change(
    db: Session,
    incident_report_id: str,
    from_status: Optional[str],
    to_status: str,
    reason: Optional[str] = None,
) -> None:
    db.execute(
        text(
            """INSERT INTO incident_status_history (incident_report_id, from_status, to_status, reason)
               VALUES (:iid, :from_status, :to_status, :reason)"""
        ),
        {
            "iid": incident_report_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
        },
    )
    log_audit_event(
        db,
        event_type="incident.status_changed",
        entity_type="incident_report",
        entity_id=incident_report_id,
        actor_type="system",
        actor_id=None,
        payload={"from": from_status, "to": to_status, "reason": reason},
    )
    db.commit()


# Step 3: store all acknowledgements.
def log_acknowledgement(
    db: Session, incident_route_id: str, ack_status: str, ack_time: str
) -> None:
    db.execute(
        text(
            "UPDATE incident_routes SET ack_status = :status, ack_time = :ack_time WHERE id = :id"
        ),
        {"status": ack_status, "ack_time": ack_time, "id": incident_route_id},
    )
    result = db.execute(
        text("SELECT incident_report_id, target_type FROM incident_routes WHERE id = :id"),
        {"id": incident_route_id},
    )
    row = result.mappings().first()
    if row:
        log_audit_event(
            db,
            event_type="incident.ack_received",
            entity_type="incident_route",
            entity_id=incident_route_id,
            actor_type="system",
            actor_id=None,
            payload={
                "incident_report_id": row["incident_report_id"],
                "target_type": row["target_type"],
                "ack_status": ack_status,
            },
        )
    db.commit()


# Step 4: compute mean response time (dispatch -> ack, across all route targets).
def compute_mean_response_time(db: Session, window_days: int) -> MeanResponseTimeResult:
    result = db.execute(
        text(
            """SELECT EXTRACT(EPOCH FROM (ack_time - routed_at)) as response_s
               FROM incident_routes
               WHERE routed_at >= now() - (:days || ' days')::interval
                 AND ack_time IS NOT NULL"""
        ),
        {"days": window_days},
    )
    values = [float(r["response_s"]) for r in result.mappings().all()]
    mean = sum(values) / len(values) if values else 0.0
    return MeanResponseTimeResult(window_days=window_days, mean_response_time_s=mean, sample_size=len(values))


# Step 5 + 6: alert accuracy + false positive rate.
# True positive: hazard_alert whose geom+validity window overlaps at least one
# incident_report within that window. False positive: no matching incident.
def compute_alert_accuracy(db: Session, window_days: int) -> AlertAccuracyResult:
    result = db.execute(
        text(
            """SELECT
                 ha.id,
                 EXISTS (
                   SELECT 1 FROM incident_reports ir
                   WHERE ir.created_at BETWEEN ha.valid_from AND COALESCE(ha.valid_to, now())
                     AND ST_Intersects(ir.geom, ha.geom)
                 ) as matched_incident
               FROM hazard_alerts ha
               WHERE ha.issued_at >= now() - (:days || ' days')::interval"""
        ),
        {"days": window_days},
    )
    rows = result.mappings().all()
    total = len(rows)
    true_positive = sum(1 for r in rows if r["matched_incident"])
    false_positive = total - true_positive

    return AlertAccuracyResult(
        window_days=window_days,
        total_alerts=total,
        true_positive_alerts=true_positive,
        false_positive_alerts=false_positive,
        accuracy=(true_positive / total) if total else 0.0,
        false_positive_rate=(false_positive / total) if total else 0.0,
    )


# Step 7: missed warning rate — incident occurred with no active hazard_alert covering it.
def compute_missed_warning_rate(db: Session, window_days: int) -> MissedWarningResult:
    result = db.execute(
        text(
            """SELECT
                 ir.id,
                 EXISTS (
                   SELECT 1 FROM hazard_alerts ha
                   WHERE ir.created_at BETWEEN ha.valid_from AND COALESCE(ha.valid_to, now())
                     AND ST_Intersects(ir.geom, ha.geom)
                 ) as had_active_alert
               FROM incident_reports ir
               WHERE ir.created_at >= now() - (:days || ' days')::interval"""
        ),
        {"days": window_days},
    )
    rows = result.mappings().all()
    total = len(rows)
    missed = sum(1 for r in rows if not r["had_active_alert"])

    return MissedWarningResult(
        window_days=window_days,
        total_incidents=total,
        missed_incidents=missed,
        missed_warning_rate=(missed / total) if total else 0.0,
    )


# Step 8: refit thresholds manually after review. Does NOT auto-apply — only computes
# and records a recommendation for human review (Module 17 enforces admin-only manual
# application via risk-rule tuning).
def generate_threshold_refit_recommendations(
    db: Session, window_days: int
) -> list[ThresholdRefitRecommendation]:
    result = db.execute(
        text(
            """SELECT
                 ir.beach_id,
                 bap.activity_type,
                 bap.min_safe_wave_height,
                 count(*) as incident_count,
                 avg((ir.current_hazard_context->>'wave_height_m')::numeric) as avg_wave_height_at_incident
               FROM incident_reports ir
               JOIN beach_activity_profiles bap ON bap.beach_id = ir.beach_id AND bap.activity_type = ir.activity_type
               WHERE ir.created_at >= now() - (:days || ' days')::interval
                 AND ir.current_hazard_context ? 'wave_height_m'
               GROUP BY ir.beach_id, bap.activity_type, bap.min_safe_wave_height
               HAVING count(*) >= 3"""
        ),
        {"days": window_days},
    )
    rows = result.mappings().all()

    recs = [
        ThresholdRefitRecommendation(
            beach_id=str(r["beach_id"]),
            activity_type=r["activity_type"],
            rule_parameter="min_safe_wave_height",
            current_value=float(r["min_safe_wave_height"]) if r["min_safe_wave_height"] else None,
            recommended_value=float(r["avg_wave_height_at_incident"]),
            justification=(
                f"{r['incident_count']} incidents in last {window_days}d occurred at avg wave "
                f"height {float(r['avg_wave_height_at_incident']):.2f}m, below/near current "
                f"threshold — suggests threshold is too permissive."
            ),
            based_on_incident_count=int(r["incident_count"]),
        )
        for r in rows
    ]

    for rec in recs:
        log_audit_event(
            db,
            event_type="analytics.threshold_refit_recommended",
            entity_type="beach_activity_profile",
            entity_id=rec.beach_id,
            actor_type="system",
            actor_id=None,
            payload=rec.model_dump(),
        )
    db.commit()

    return recs
