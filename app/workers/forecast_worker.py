# """
# app/workers/forecast_worker.py
# Beat calls sync_forecasts() periodically — fetches Open-Meteo marine+weather
# forecast for every active beach and stores via forecast_engine.open_meteo_connector.
# NEW, additive file. Does not modify ingestion_worker.py or any existing worker.
# """
# from __future__ import annotations

# import logging

# from celery import shared_task
# from sqlalchemy import select, func

# from app.core.db import get_session
# from app.models.geospatial import Beach
# from forecast_engine.open_meteo_connector import sync_beach_forecast

# logger = logging.getLogger(__name__)


# @shared_task(name="workers.forecast.sync_forecasts")
# def sync_forecasts(forecast_days: int = 7) -> dict:
#     # centroid is nullable — fall back to ST_Centroid(geom) since geom is NOT NULL.
#     # This derives the point geometrically from real stored polygon data, not invented.
#     lat_expr = func.ST_Y(func.coalesce(Beach.centroid, func.ST_Centroid(Beach.geom)))
#     lon_expr = func.ST_X(func.coalesce(Beach.centroid, func.ST_Centroid(Beach.geom)))

#     with get_session() as db:
#         beaches = db.execute(
#             select(Beach.id, lat_expr.label("lat"), lon_expr.label("lon"))
#             .where(Beach.active == True)
#         ).all()

#     summary = {}
#     for beach_id, lat, lon in beaches:
#         try:
#             inserted = sync_beach_forecast(beach_id, lat, lon, forecast_days=forecast_days)
#             summary[str(beach_id)] = {"inserted": inserted}
#         except Exception:
#             logger.exception("forecast_worker.sync_failed beach_id=%s", beach_id)
#             summary[str(beach_id)] = {"error": "unhandled_exception"}
#     return summary








"""
app/workers/forecast_worker.py
Beat calls sync_forecasts() periodically — fetches Open-Meteo marine+weather
forecast for every active beach and stores via forecast_engine.open_meteo_connector.
NEW, additive file. Does not modify ingestion_worker.py or any existing worker.
"""
from __future__ import annotations

import logging

from celery import shared_task
from sqlalchemy import select, func

from app.core.db import get_session
from app.models.geospatial import Beach
from forecast_engine.open_meteo_connector import sync_beach_forecast

logger = logging.getLogger(__name__)


@shared_task(name="workers.forecast.sync_forecasts")
def sync_forecasts(forecast_days: int = 7) -> dict:
    # centroid is nullable — fall back to ST_Centroid(geom) since geom is NOT NULL.
    lat_expr = func.ST_Y(func.coalesce(Beach.centroid, func.ST_Centroid(Beach.geom)))
    lon_expr = func.ST_X(func.coalesce(Beach.centroid, func.ST_Centroid(Beach.geom)))

    with get_session() as db:
        beaches = db.execute(
            select(Beach.id, lat_expr.label("lat"), lon_expr.label("lon"))
            .where(Beach.active == True)
        ).all()

    summary = {}
    for beach_id, lat, lon in beaches:
        try:
            inserted = sync_beach_forecast(beach_id, lat, lon, forecast_days=forecast_days)
            summary[str(beach_id)] = {"inserted": inserted}
        except Exception:
            logger.exception("forecast_worker.sync_failed beach_id=%s", beach_id)
            summary[str(beach_id)] = {"error": "unhandled_exception"}
    return summary