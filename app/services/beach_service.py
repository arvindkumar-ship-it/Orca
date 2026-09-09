# # MODULE 19: API Layer — Beaches, Risk, Forecast — Service
# # Thin read layer: does NOT reimplement scoring — calls Module 5 (risk_engine) and
# # Module 6 (forecast_engine) services directly, per those modules' own deliverables.

# import json

# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.services.risk_engine import compute_beach_activity_risk  # Module 5
# from app.services.forecast_engine import get_forecast_timeline  # Module 6
# from app.schemas.beach import (
#     BeachSearchItem,
#     BeachDetail,
#     SafeZoneRef,
#     JurisdictionRef,
#     RiskResponse,
#     RiskExplanation,
#     ForecastItem,
#     AlertItem,
# )


# # GET /v1/beaches — spatial search + latest risk snapshot join.
# async def search_beaches(
#     db: AsyncSession,
#     state: str | None,
#     near: tuple[float, float] | None,  # (lat, lng)
#     radius_m: int | None,
#     activity: str | None,
# ) -> list[BeachSearchItem]:
#     conditions = ["b.active = true"]
#     params: dict = {}

#     if state:
#         conditions.append("b.state = :state")
#         params["state"] = state

#     distance_select = "NULL as distance_m"
#     order_by = "b.name ASC"
#     if near:
#         lat, lng = near
#         params["lat"] = lat
#         params["lng"] = lng
#         distance_select = (
#             "ST_Distance(b.geom::geography, "
#             "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) as distance_m"
#         )
#         order_by = "distance_m ASC"
#         if radius_m:
#             params["radius_m"] = radius_m
#             conditions.append(
#                 "ST_DWithin(b.geom::geography, "
#                 "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)"
#             )

#     if activity:
#         params["activity"] = activity
#         activity_join = """LEFT JOIN LATERAL (
#             SELECT risk_score, verdict FROM beach_risk_scores brs
#             WHERE brs.beach_id = b.id AND brs.activity_type = :activity
#             ORDER BY brs.forecast_time DESC LIMIT 1
#         ) rs ON true"""
#     else:
#         activity_join = """LEFT JOIN LATERAL (
#             SELECT risk_score, verdict FROM beach_risk_scores brs
#             WHERE brs.beach_id = b.id
#             ORDER BY brs.forecast_time DESC LIMIT 1
#         ) rs ON true"""

#     result = await db.execute(
#         text(
#             f"""SELECT b.id, b.name, b.state, b.district, b.has_lifeguard, {distance_select},
#                        rs.verdict as current_verdict, rs.risk_score as current_risk_score
#                 FROM beaches b
#                 {activity_join}
#                 WHERE {' AND '.join(conditions)}
#                 ORDER BY {order_by}
#                 LIMIT 50"""
#         ),
#         params,
#     )
#     rows = result.mappings().all()

#     return [
#         BeachSearchItem(
#             id=r["id"],
#             name=r["name"],
#             state=r["state"],
#             district=r["district"],
#             distance_m=round(r["distance_m"]) if r["distance_m"] is not None else None,
#             has_lifeguard=r["has_lifeguard"],
#             current_verdict=r["current_verdict"],
#             current_risk_score=float(r["current_risk_score"]) if r["current_risk_score"] is not None else None,
#         )
#         for r in rows
#     ]


# # GET /v1/beaches/{id} — detail page.
# async def get_beach_detail(db: AsyncSession, beach_id: str) -> BeachDetail | None:
#     result = await db.execute(
#         text(
#             """SELECT id, name, state, district, has_lifeguard, public_access, ST_AsGeoJSON(geom) as geom
#                FROM beaches WHERE id = :id AND active = true"""
#         ),
#         {"id": beach_id},
#     )
#     beach_row = result.mappings().first()
#     if not beach_row:
#         return None

#     zones_result = await db.execute(
#         text(
#             """SELECT id, name,
#                       ST_Distance(geom::geography, (SELECT centroid FROM beaches WHERE id=:id)::geography) as distance_m
#                FROM safe_zones WHERE beach_id = :id AND active = true
#                ORDER BY distance_m ASC"""
#         ),
#         {"id": beach_id},
#     )
#     safe_zones = zones_result.mappings().all()

#     juris_result = await db.execute(
#         text(
#             """SELECT j.id, j.name FROM jurisdictions j, beaches b
#                WHERE b.id = :id AND ST_Intersects(j.service_area_geom, b.geom) AND j.active = true
#                ORDER BY j.escalation_level ASC LIMIT 1"""
#         ),
#         {"id": beach_id},
#     )
#     jurisdiction = juris_result.mappings().first()

#     return BeachDetail(
#         id=str(beach_row["id"]),
#         name=beach_row["name"],
#         state=beach_row["state"],
#         district=beach_row["district"],
#         geom=json.loads(beach_row["geom"]),
#         has_lifeguard=beach_row["has_lifeguard"],
#         public_access=beach_row["public_access"],
#         safe_zones=[
#             SafeZoneRef(id=str(z["id"]), name=z["name"], distance_m=round(z["distance_m"]))
#             for z in safe_zones
#         ],
#         jurisdiction=JurisdictionRef(id=str(jurisdiction["id"]), name=jurisdiction["name"])
#         if jurisdiction
#         else None,
#     )


# # GET /v1/beaches/{id}/risk — delegates entirely to Module 5 risk engine, which itself:
# # loads profiles, applies hard overrides, computes+stores snapshot.
# async def get_beach_risk(db: AsyncSession, beach_id: str, activity_type: str) -> RiskResponse:
#     result = await compute_beach_activity_risk(db, beach_id, activity_type)
#     return RiskResponse(
#         beach_id=beach_id,
#         activity_type=activity_type,
#         forecast_time=result.forecast_time,
#         risk_score=result.risk_score,
#         verdict=result.verdict,
#         hard_override_reason=result.hard_override_reason,
#         explanation=RiskExplanation(top_factors=result.explanation.top_factors),
#     )


# # GET /v1/beaches/{id}/forecast — delegates to Module 6 forecast engine.
# async def get_beach_forecast(
#     db: AsyncSession, beach_id: str, activity_type: str, hours: int
# ) -> list[ForecastItem]:
#     timeline = await get_forecast_timeline(db, beach_id, activity_type, hours)
#     return [
#         ForecastItem(
#             forecast_time=slot.forecast_time,
#             wave_height=slot.wave_height,
#             current_speed=slot.current_speed,
#             wind_speed=slot.wind_speed,
#             risk_score=slot.risk_score,
#             verdict=slot.verdict,
#         )
#         for slot in timeline
#     ]


# # GET /v1/alerts — active official alerts near a point.
# async def get_active_alerts(
#     db: AsyncSession, lat: float, lng: float, radius_m: int
# ) -> list[AlertItem]:
#     result = await db.execute(
#         text(
#             """SELECT id, alert_type, severity, title, valid_from, valid_to
#                FROM hazard_alerts
#                WHERE status = 'active'
#                  AND (valid_to IS NULL OR valid_to > now())
#                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)
#                ORDER BY
    # CASE severity
    #     WHEN 'extreme' THEN 1
    #     WHEN 'severe' THEN 2
    #     WHEN 'moderate' THEN 3
    #     WHEN 'minor' THEN 4
    #     WHEN 'info' THEN 5
    #     ELSE 6
    # END,
    # issued_at DESC
#                LIMIT 100"""
#         ),
#         {"lat": lat, "lng": lng, "radius_m": radius_m},
#     )
#     return [AlertItem(**dict(r)) for r in result.mappings().all()]









# MODULE 19: API Layer — Beaches, Risk, Forecast — Service
# Thin read layer: does NOT reimplement scoring — calls Module 5 (risk_engine) and
# Module 6 (forecast_engine) services directly, per those modules' own deliverables.
#
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.
#
# ⚠️ FLAGGED IMPORT PATH ISSUE (not part of B1, but will break at import time): this file
# imports `from app.services.risk_engine import compute_beach_activity_risk` and
# `from app.services.forecast_engine import get_forecast_timeline` — but per your project's
# own folder scaffold (Part A1), Module 5 and 6 were copied to `backend/risk_engine/` and
# `backend/forecast_engine/` as TOP-LEVEL packages (siblings of `app/`), not nested under
# `app/services/`. The two imports below are updated to `from risk_engine... import ...` /
# `from forecast_engine... import ...` to match that actual folder layout — but I don't have
# Module 5/6's zips to verify the exact submodule/filename inside those packages (e.g.
# risk_engine/engine.py vs risk_engine/__init__.py). If `compute_beach_activity_risk` and
# `get_forecast_timeline` live in a specific file inside those packages rather than being
# re-exported at the package root, adjust the import path accordingly.

import json

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from risk_engine.engine import compute_and_store_risk # Module 5 — verify actual submodule path
from forecast_engine.engine import compute_forecast_outlook  # Module 6 — verify actual submodule path
from app.schemas.beach import (
    BeachSearchItem,
    BeachDetail,
    SafeZoneRef,
    JurisdictionRef,
    RiskResponse,
    RiskExplanation,
    ForecastItem,
    AlertItem,
)


# GET /v1/beaches — spatial search + latest risk snapshot join.
def search_beaches(
    db: Session,
    state: str | None,
    near: tuple[float, float] | None,  # (lat, lng)
    radius_m: int | None,
    activity: str | None,
) -> list[BeachSearchItem]:
    conditions = ["b.active = true"]
    params: dict = {}

    if state:
        conditions.append("b.state = :state")
        params["state"] = state

    distance_select = "NULL as distance_m"
    order_by = "b.name ASC"
    if near:
        lat, lng = near
        params["lat"] = lat
        params["lng"] = lng
        distance_select = (
            "ST_Distance(b.geom::geography, "
            "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) as distance_m"
        )
        order_by = "distance_m ASC"
        if radius_m:
            params["radius_m"] = radius_m
            conditions.append(
                "ST_DWithin(b.geom::geography, "
                "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)"
            )

    if activity:
        params["activity"] = activity
        activity_join = """LEFT JOIN LATERAL (
            SELECT risk_score, verdict FROM beach_risk_scores brs
            WHERE brs.beach_id = b.id AND brs.activity_type = :activity
            ORDER BY brs.forecast_time DESC LIMIT 1
        ) rs ON true"""
    else:
        activity_join = """LEFT JOIN LATERAL (
            SELECT risk_score, verdict FROM beach_risk_scores brs
            WHERE brs.beach_id = b.id
            ORDER BY brs.forecast_time DESC LIMIT 1
        ) rs ON true"""

    result = db.execute(
        text(
            f"""SELECT b.id, b.name, b.state, b.district, b.has_lifeguard, {distance_select},
                       rs.verdict as current_verdict, rs.risk_score as current_risk_score
                FROM beaches b
                {activity_join}
                WHERE {' AND '.join(conditions)}
                ORDER BY {order_by}
                LIMIT 50"""
        ),
        params,
    )
    rows = result.mappings().all()

    return [
        BeachSearchItem(
            id=str(r["id"]),
            name=r["name"],
            state=r["state"],
            district=r["district"],
            distance_m=round(r["distance_m"]) if r["distance_m"] is not None else None,
            has_lifeguard=r["has_lifeguard"],
            current_verdict=r["current_verdict"],
            current_risk_score=float(r["current_risk_score"]) if r["current_risk_score"] is not None else None,
        )
        for r in rows
    ]


# GET /v1/beaches/{id} — detail page.
def get_beach_detail(db: Session, beach_id: str) -> BeachDetail | None:
    result = db.execute(
        text(
            """SELECT id, name, state, district, has_lifeguard, public_access, ST_AsGeoJSON(geom) as geom
               FROM beaches WHERE id = :id AND active = true"""
        ),
        {"id": beach_id},
    )
    beach_row = result.mappings().first()
    if not beach_row:
        return None

    zones_result = db.execute(
        text(
            """SELECT id, name,
                        ST_Distance(geom::geography, (SELECT COALESCE(centroid, ST_Centroid(geom)) FROM beaches WHERE id=:id)::geography) as distance_m
                      
               FROM safe_zones WHERE beach_id = :id AND active = true
               ORDER BY distance_m ASC"""
        ),
        {"id": beach_id},
    )
    safe_zones = zones_result.mappings().all()

    juris_result = db.execute(
        text(
            """SELECT j.id, j.name FROM jurisdictions j, beaches b
               WHERE b.id = :id AND ST_Intersects(j.service_area_geom, b.geom) AND j.active = true
               ORDER BY j.escalation_level ASC LIMIT 1"""
        ),
        {"id": beach_id},
    )
    jurisdiction = juris_result.mappings().first()

    return BeachDetail(
        id=str(beach_row["id"]),
        name=beach_row["name"],
        state=beach_row["state"],
        district=beach_row["district"],
        geom=json.loads(beach_row["geom"]),
        has_lifeguard=beach_row["has_lifeguard"],
        public_access=beach_row["public_access"],
        safe_zones=[
            SafeZoneRef(id=str(z["id"]), name=z["name"], distance_m=round(z["distance_m"]))
            for z in safe_zones
        ],
        jurisdiction=JurisdictionRef(id=str(jurisdiction["id"]), name=jurisdiction["name"])
        if jurisdiction
        else None,
    )


# GET /v1/beaches/{id}/risk — delegates entirely to Module 5 risk engine, which itself:
# loads profiles, applies hard overrides, computes+stores snapshot.
def get_beach_risk(db: Session, beach_id: str, activity_type: str) -> RiskResponse:
    result = compute_and_store_risk(beach_id, activity_type)
    if not result:
        raise HTTPException(status_code=404, detail="risk could not be computed for this beach/activity")
    return RiskResponse(
        beach_id=beach_id,
        activity_type=activity_type,
        forecast_time=result.get("forecast_time"),
        risk_score=result.get("risk_score"),
        verdict=result.get("verdict"),
        hard_override_reason=result.get("hard_override_reason"),
        explanation=RiskExplanation(top_factors=result.get("explanation", {}).get("top_factors", [])),
    )


# GET /v1/beaches/{id}/forecast — delegates to Module 6 forecast engine.
def get_beach_forecast(
    db: Session, beach_id: str, activity_type: str, hours: int
) -> list[ForecastItem]:
    result = compute_forecast_outlook(beach_id, activity_type)
    # ⚠️ ASSUMPTION — result shape not verified against actual return statement in
    # forecast_engine/engine.py's compute_forecast_outlook(). It likely returns something
    # built from outlook.py's ForecastOutlook (build_outlook) rather than a flat list of
    # points. If this errors, check engine.py's return statement and outlook.py's
    # ForecastOutlook/RiskPoint shape and adjust the mapping below.
    points = result.get("points", [])
    return [
        ForecastItem(
            forecast_time=p.get("forecast_time"),
            wave_height=p.get("wave_height"),
            current_speed=p.get("current_speed"),
            wind_speed=p.get("wind_speed"),
            risk_score=p.get("risk_score"),
            verdict=p.get("verdict"),
        )
        for p in points
    ]


# GET /v1/alerts — active official alerts near a point.
def get_active_alerts(
    db: Session, lat: float, lng: float, radius_m: int
) -> list[AlertItem]:
    result = db.execute(
        text(
            """SELECT id, alert_type, severity, title, valid_from, valid_to
               FROM hazard_alerts
               WHERE status = 'active'
                 AND (valid_to IS NULL OR valid_to > now())
                 AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)
               ORDER BY
    CASE severity
        WHEN 'extreme' THEN 1
        WHEN 'severe' THEN 2
        WHEN 'moderate' THEN 3
        WHEN 'minor' THEN 4
        WHEN 'info' THEN 5
        ELSE 6
    END,
    issued_at DESC
               LIMIT 100"""
        ),
        {"lat": lat, "lng": lng, "radius_m": radius_m},
    )
    return [AlertItem(**dict(r)) for r in result.mappings().all()]