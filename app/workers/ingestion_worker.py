"""
app/workers/ingestion_worker.py
Beat calls poll_sources() every 60s â€” runs all polled connectors (INCOIS, SACHET).
manual_admin excluded â€” event-driven, called directly from admin API, not polled.
"""
from __future__ import annotations

import logging

import redis
from celery import shared_task

from app.core.config import settings as app_settings  # ASSUMPTION: REDIS_URL field name â€” verify
from app.services.ingestion_service import build_connectors, run_connector

logger = logging.getLogger(__name__)


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(app_settings.REDIS_URL)  # ASSUMPTION â€” verify field name in config.py


@shared_task(name="workers.ingestion.poll_sources")
def poll_sources() -> dict:
    redis_client = _redis_client()
    summary = {}
    for connector in build_connectors():
        try:
            result = run_connector(connector, redis_client)
            summary[connector.source.value] = {
                "fetched": len(result.records),
                "rejected": result.rejected_count,
                "error": result.error,
            }
        except Exception:
            logger.exception("ingestion_worker.poll_failed source=%s", connector.source.value)
            summary[connector.source.value] = {"error": "unhandled_exception"}
    return summary
