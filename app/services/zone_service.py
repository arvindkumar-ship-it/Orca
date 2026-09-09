"""
ORCA — GENERALIZE of app/services/beach_service.py.

Thin read layer: does NOT reimplement scoring — calls risk_engine (Module 5,
generalized: beach_id->zone_id, see PROGRESS.md Section A) and forecast_engine
(Module 6, COPY, unchanged) directly, exactly like the original file's own
documented contract.

Renames: search_beaches->search_zones, get_beach_detail->get_zone_detail,
get_beach_risk->get_zone_risk, get_beach_forecast->get_zone_forecast,
get_active_alerts kept as-is (hazard_alerts table is unchanged, source-agnostic).
beach_risk_scores -> zone_risk_scores, beaches -> marine_zones,
safe_zones/beach_id -> safe_harbors/marine_zone_id.

Sync SQLAlchemy throughout (WaveSafe's project-wide B1 decision, inherited
unchanged — see beach_service.py's own header comment for why).
"""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from risk_engine.engine import compute_and_store_risk  # generalized signature: (zone_id, activity_type)
from forecast_engine.zone_engine import compute_forecast_outlook  # fixed during merge — see that file's docstring
from app.schemas.zone import (
    ZoneSearchItem,
    ZoneDetail,
    SafeHarborRef,
    JurisdictionRef,
    RiskResponse,
    RiskExplanation,
    ForecastItem,
    AlertItem,
)


def search_zones(
    db: Session,
    state: str | None,
    near: tuple[float, float] | None,
    radius_m: int | None,
    activity: str | None,
    zone_type: str | None = None,
) -> list[ZoneSearchItem]:
    conditions = ["z.active = true"]
    params: dict = {}

    if state:
        conditions.append("z.state = :state")
        params["state"] = state
    if zone_type:
        conditions.append("z.zone_type = :zone_type")
        params["zone_type"] = zone_type

    distance_select = "NULL as distance_m"
    order_by = "z.name ASC"
    if near:
        lat, lng = near
        params["lat"] = lat
        params["lng"] = lng
        distance_select = (
            "ST_Distance(z.geom::geography, "
            "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography) as distance_m"
        )
        order_by = "distance_m ASC"
        if radius_m:
            params["radius_m"] = radius_m
            conditions.append(
                "ST_DWithin(z.geom::geography, "
                "ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)"
            )

    activity_filter = "AND brs.activity_type = :activity" if activity else ""
    if activity:
        params["activity"] = activity
    activity_join = f"""LEFT JOIN LATERAL (
        SELECT risk_score, verdict FROM zone_risk_scores brs
        WHERE brs.zone_id = z.id {activity_filter}
        ORDER BY brs.forecast_time DESC LIMIT 1
    ) rs ON true"""

    rows = db.execute(
        text(
            f"""SELECT z.id, z.name, z.zone_type, z.state, z.district, z.depth_m, {distance_select},
                       rs.verdict as current_verdict, rs.risk_score as current_risk_score
                FROM marine_zones z
                {activity_join}
                WHERE {' AND '.join(conditions)}
                ORDER BY {order_by}
                LIMIT 50"""
        ),
        params,
    ).mappings().all()

    return [
        ZoneSearchItem(
            id=str(r["id"]), name=r["name"], zone_type=r["zone_type"], state=r["state"],
            district=r["district"], distance_m=round(r["distance_m"]) if r["distance_m"] is not None else None,
            depth_m=float(r["depth_m"]) if r["depth_m"] is not None else None,
            current_verdict=r["current_verdict"],
            current_risk_score=float(r["current_risk_score"]) if r["current_risk_score"] is not None else None,
        )
        for r in rows
    ]


def get_zone_detail(db: Session, zone_id: str) -> ZoneDetail | None:
    zone_row = db.execute(
        text("""SELECT id, name, zone_type, state, district, depth_m, public_access, ST_AsGeoJSON(geom) as geom
                 FROM marine_zones WHERE id = :id AND active = true"""),
        {"id": zone_id},
    ).mappings().first()
    if not zone_row:
        return None

    harbors = db.execute(
        text("""SELECT id, name,
                        ST_Distance(geom::geography,
                            (SELECT COALESCE(centroid, ST_Centroid(geom)) FROM marine_zones WHERE id=:id)::geography
                        ) as distance_m
                 FROM safe_harbors WHERE marine_zone_id = :id AND active = true
                 ORDER BY distance_m ASC"""),
        {"id": zone_id},
    ).mappings().all()

    jurisdiction = db.execute(
        text("""SELECT j.id, j.name FROM jurisdictions j, marine_zones z
                 WHERE z.id = :id AND ST_Intersects(j.service_area_geom, z.geom) AND j.active = true
                 ORDER BY j.escalation_level ASC LIMIT 1"""),
        {"id": zone_id},
    ).mappings().first()

    return ZoneDetail(
        id=str(zone_row["id"]), name=zone_row["name"], zone_type=zone_row["zone_type"],
        state=zone_row["state"], district=zone_row["district"], geom=json.loads(zone_row["geom"]),
        depth_m=float(zone_row["depth_m"]) if zone_row["depth_m"] is not None else None,
        public_access=zone_row["public_access"],
        safe_harbors=[SafeHarborRef(id=str(h["id"]), name=h["name"], distance_m=round(h["distance_m"])) for h in harbors],
        jurisdiction=JurisdictionRef(id=str(jurisdiction["id"]), name=jurisdiction["name"]) if jurisdiction else None,
    )


def get_zone_risk(db: Session, zone_id: str, activity_type: str) -> RiskResponse:
    result = compute_and_store_risk(zone_id, activity_type)
    if not result:
        raise HTTPException(status_code=404, detail="risk could not be computed for this zone/activity")
    return RiskResponse(
        zone_id=zone_id, activity_type=activity_type, forecast_time=result.get("forecast_time"),
        risk_score=result.get("risk_score"), verdict=result.get("verdict"),
        hard_override_reason=result.get("hard_override_reason"),
        explanation=RiskExplanation(top_factors=result.get("explanation", {}).get("top_factors", [])),
    )


def get_zone_forecast(db: Session, zone_id: str, activity_type: str, hours: int) -> list[ForecastItem]:
    result = compute_forecast_outlook(zone_id, activity_type)
    points = result.get("points", [])
    return [
        ForecastItem(
            forecast_time=p.get("forecast_time"), wave_height=p.get("wave_height"),
            current_speed=p.get("current_speed"), wind_speed=p.get("wind_speed"),
            risk_score=p.get("risk_score"), verdict=p.get("verdict"),
        )
        for p in points
    ]


def get_active_alerts(db: Session, lat: float, lng: float, radius_m: int) -> list[AlertItem]:
    rows = db.execute(
        text("""SELECT id, alert_type, severity, title, valid_from, valid_to
                 FROM hazard_alerts
                 WHERE status = 'active' AND (valid_to IS NULL OR valid_to > now())
                   AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius_m)
                 ORDER BY
                   CASE severity WHEN 'extreme' THEN 1 WHEN 'severe' THEN 2 WHEN 'moderate' THEN 3
                                 WHEN 'minor' THEN 4 WHEN 'info' THEN 5 ELSE 6 END,
                   issued_at DESC
                 LIMIT 100"""),
        {"lat": lat, "lng": lng, "radius_m": radius_m},
    ).mappings().all()
    return [AlertItem(**dict(r)) for r in rows]
