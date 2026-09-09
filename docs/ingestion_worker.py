"""
Module 3 + 4 — Ingestion Worker

Wires the full pipeline end-to-end, one Celery task per source:
    connector.fetch()
        -> Deduplicator.filter_new()
        -> raw_storage.store_raw_payload()   (raw, untouched)
        -> NormalizationEngine.normalize()   (Module 4)
        -> persistence.persist()             (writes hazard_alerts / beach_forecasts
                                               + publishes risk-engine recompute event)
        -> ops_alerts.check_and_alert()      (on repeated failure)

ASSUMPTION — verify against real repo:
Celery app instance imported from `app.celery_app` as `celery_app`, and a
shared Redis client from `app.redis_client` as `redis_client`. If your
project wires Celery/Redis differently (different module path, different
broker), only the two imports below need to change — task bodies are
otherwise stack-agnostic.
"""
from __future__ import annotations

import logging

from app.celery_app import celery_app       # ASSUMPTION — see docstring
from app.redis_client import redis_client   # ASSUMPTION — see docstring

from ingestion.config import settings
from ingestion.dedup import Deduplicator
from ingestion.incois_connector import IncoisConnector
from ingestion.manual_connector import ManualAdminConnector
from ingestion.ops_alerts import check_and_alert
from ingestion.persistence import persist
from ingestion.raw_storage import store_raw_payload
from ingestion.sachet_connector import SachetConnector
from ingestion.schemas import IngestionRunResult
from normalization.normalizer import NormalizationEngine

logger = logging.getLogger("workers.ingestion_worker")

_deduplicator = Deduplicator(redis_client)
_normalizer = NormalizationEngine()


def _process_result(result: IngestionRunResult, connector) -> dict:
    new_records = _deduplicator.filter_new(result.records)
    persisted, dropped = 0, 0

    for record in new_records:
        store_raw_payload(record)  # step 6 — always store raw, even if normalization later fails

        canonical_event = _normalizer.normalize(record)
        if canonical_event is None:
            dropped += 1
            continue

        row_id = persist(canonical_event, redis_client)
        if row_id is None:
            dropped += 1
        else:
            persisted += 1

    check_and_alert(connector)

    summary = {
        "source": result.source.value,
        "fetched": len(result.records),
        "deduped_out": len(result.records) - len(new_records),
        "persisted": persisted,
        "dropped": dropped,
        "rejected_at_ingestion": result.rejected_count,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }
    logger.info("ingestion_worker.run_summary %s", summary)
    return summary


@celery_app.task(name="ingestion.poll_incois", bind=True, max_retries=0)
def poll_incois(self):
    connector = IncoisConnector(settings.sources["incois"])
    result = connector.fetch()
    return _process_result(result, connector)


@celery_app.task(name="ingestion.poll_sachet", bind=True, max_retries=0)
def poll_sachet(self):
    connector = SachetConnector(settings.sources["sachet"])
    result = connector.fetch()
    return _process_result(result, connector)


@celery_app.task(name="ingestion.submit_manual_closure", bind=True, max_retries=0)
def submit_manual_closure(self, *, admin_user_id: str, beach_id: str, reason: str,
                           severity: str, geometry: dict, valid_from=None, valid_to=None):
    """Invoked directly by the admin API handler (Module 21/22 admin console), not polled."""
    from ingestion.schemas import Severity

    connector = ManualAdminConnector(settings.sources["manual_admin"])
    record = connector.submit_closure(
        admin_user_id=admin_user_id,
        beach_id=beach_id,
        reason=reason,
        severity=Severity(severity),
        geometry=geometry,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    store_raw_payload(record)
    canonical_event = _normalizer.normalize(record)
    if canonical_event is None:
        logger.error("submit_manual_closure.normalization_failed beach_id=%s", beach_id)
        return {"status": "rejected"}
    row_id = persist(canonical_event, redis_client)
    return {"status": "persisted" if row_id else "dropped", "hazard_alert_id": row_id}


# --- Celery beat schedule (register in your celery_app config) ---
CELERY_BEAT_SCHEDULE_ENTRIES = {
    "poll-incois": {
        "task": "ingestion.poll_incois",
        "schedule": settings.sources["incois"].poll_interval_seconds,
    },
    "poll-sachet": {
        "task": "ingestion.poll_sachet",
        "schedule": settings.sources["sachet"].poll_interval_seconds,
    },
}
