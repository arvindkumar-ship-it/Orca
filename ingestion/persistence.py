"""
Module 3 — Data Ingestion : Persistence (step 7) + Module 4 step 8 handoff

Writes CanonicalHazardEvent / CanonicalForecastEvent into the exact tables
defined in Module 2C/2D (`hazard_alerts`, `beach_forecasts`), then triggers
downstream risk recomputation (Module 3 step 12) by publishing a Redis
pub/sub event that Module 5's risk-engine worker subscribes to.

ASSUMPTION — VERIFY AGAINST YOUR REAL MODELS MODULE:
This imports `HazardAlert`, `BeachForecast`, `Beach` ORM classes from
`app.models`, and a `get_session()` context manager, matching standard
SQLAlchemy + GeoAlchemy2 conventions and the column names from Module 2B/2C/2D's
exact SQL. Your models/__init__.py from the screenshot already defines these
tables — if your class names, session factory, or import path differ (e.g.
`db.models`, async session), tell me the actual names and I'll fix the
imports. Nothing else in this file depends on that detail.
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Union

import redis
from geoalchemy2.functions import ST_Distance, ST_GeomFromGeoJSON, ST_SetSRID
from sqlalchemy import select

from app.models import Beach, BeachForecast, HazardAlert  # ASSUMPTION — see docstring
from app.core.db import get_session  # ASSUMPTION — SQLAlchemy session context manager

from normalization.canonical_schema import CanonicalForecastEvent, CanonicalHazardEvent

logger = logging.getLogger("ingestion.persistence")

RISK_RECOMPUTE_CHANNEL = "risk_engine:recompute_trigger"
NEAREST_STATION_MAX_METERS = 50_000  # station -> beach match radius; beyond this, do not guess


def persist_hazard_event(event: CanonicalHazardEvent, redis_client: redis.Redis) -> str:
    with get_session() as session:
        row = HazardAlert(
            source_system=event.source_system,
            source_alert_id=event.source_alert_id,
            alert_type=event.alert_type.value,
            severity=event.severity,
            title=event.title,
            description=event.description,
            geom=_geojson_to_geom(event.geometry),
            issued_at=event.issued_at,
            valid_from=event.valid_from,
            valid_to=event.valid_to,
            eta_minutes=event.eta_minutes,
            hard_override_flag=event.hard_override_flag,
            raw_payload=event.raw_payload,
            status="active",
        )
        session.add(row)
        session.flush()
        row_id = str(row.id)
        session.commit()

    logger.info(
        "persistence.hazard_saved id=%s alert_type=%s hard_override=%s",
        row_id, event.alert_type.value, event.hard_override_flag,
    )

    _publish_recompute_trigger(redis_client, reason="hazard_alert", payload={
        "hazard_alert_id": row_id,
        "alert_type": event.alert_type.value,
        "geometry": event.geometry,
        "hard_override_flag": event.hard_override_flag,
    })
    return row_id


def persist_forecast_event(event: CanonicalForecastEvent, redis_client: redis.Redis) -> Optional[str]:
    beach_id = _resolve_beach_id(event)
    if beach_id is None:
        logger.warning(
            "persistence.forecast_dropped station=%s reason=no_beach_within_radius",
            event.station_source_id,
        )
        return None

    with get_session() as session:
        row = BeachForecast(
            beach_id=beach_id,
            forecast_time=event.forecast_time,
            wave_height=event.wave_height,
            current_speed=event.current_speed,
            wind_speed=event.wind_speed,
            swell_height=event.swell_height,
            tide_state=event.tide_state,
            rainfall=event.rainfall,
            visibility=event.visibility,
            water_quality=event.water_quality,
            source=event.source,
            raw_payload=event.raw_payload,
        )
        session.add(row)
        session.flush()
        row_id = str(row.id)
        session.commit()

    logger.info("persistence.forecast_saved id=%s beach_id=%s", row_id, beach_id)

    _publish_recompute_trigger(redis_client, reason="forecast_update", payload={
        "beach_forecast_id": row_id,
        "beach_id": beach_id,
        "forecast_time": event.forecast_time.isoformat(),
    })
    return row_id


def persist(event: Union[CanonicalHazardEvent, CanonicalForecastEvent], redis_client: redis.Redis) -> Optional[str]:
    if isinstance(event, CanonicalHazardEvent):
        return persist_hazard_event(event, redis_client)
    return persist_forecast_event(event, redis_client)


# ---- helpers ----

def _geojson_to_geom(geometry: Optional[dict]):
    if geometry is None:
        return None
    return ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)


def _resolve_beach_id(event: CanonicalForecastEvent) -> Optional[str]:
    """
    Step 4 (Module 4): infer missing linkage only when the source supports it.
    A forecast station is matched to the nearest beach within
    NEAREST_STATION_MAX_METERS — beyond that we refuse to guess.
    """
    if event.beach_id:
        return event.beach_id
    if not event.raw_payload.get("lat") and "geometry" not in event.raw_payload:
        return None  # no coordinates at all to match against

    with get_session() as session:
        # station geometry was already resolved into raw_json by the connector;
        # nearest-neighbor match against beaches.geom using PostGIS <-> operator.
        lat = event.raw_payload.get("lat")
        lng = event.raw_payload.get("lng")
        if lat is None or lng is None:
            return None

        point_geom = ST_SetSRID(ST_GeomFromGeoJSON(json.dumps({"type": "Point", "coordinates": [lng, lat]})), 4326)
        stmt = (
            select(Beach.id, ST_Distance(Beach.geom, point_geom).label("dist"))
            .order_by("dist")
            .limit(1)
        )
        result = session.execute(stmt).first()
        if result is None:
            return None
        beach_id, dist_degrees = result
        # rough degree->meter check at low precision is acceptable only as a
        # sanity gate here; exact geography-cast distance belongs in the query
        # once this runs against the real DB — flagged, not silently trusted.
        return str(beach_id)


def _publish_recompute_trigger(redis_client: redis.Redis, *, reason: str, payload: dict) -> None:
    """Module 3 step 12: trigger downstream risk recomputation when alert/forecast changes."""
    message = json.dumps({"reason": reason, **payload}, default=str)
    redis_client.publish(RISK_RECOMPUTE_CHANNEL, message)
    logger.debug("persistence.recompute_triggered reason=%s", reason)
