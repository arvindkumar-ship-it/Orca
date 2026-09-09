# # # B10 — app.services.ingestion_service, imported by app/workers/ingestion_worker.py
# # # (the Module 26 16-line thin-wrapper version): poll_incois(db), poll_sachet(db).
# # #
# # # ⚠️ MAJOR ASSUMPTION — Module 3's ingestion/*.py connector files (9 files) were never
# # # uploaded to me in this conversation, only described in the planning doc (INCOIS poller,
# # # SACHET poller, dedup, raw storage). I cannot verify their exact function names/signatures,
# # # so this file is a best-effort wrapper based on the doc's description of what Module 3
# # # contains, NOT verified against real code like everything else I've written today.
# # #
# # # TO FIX PROPERLY: open backend/ingestion/*.py (the 9 files you copied from m03-04.zip) and
# # # tell me the actual function names for "fetch INCOIS data", "fetch SACHET data", "dedup",
# # # "normalize", "persist" — I'll rewrite this file against the real signatures in one pass,
# # # same as I did for dispatch_service.py above once I had sos_service.py's real code.
# # #
# # # Structure below follows the reference 127-line ingestion_worker.py (Module 3's original,
# # # which you kept in docs/ as reference per the earlier instruction) — this just moves that
# # # same orchestration logic into a service function instead of a worker task, per B10.

# # from sqlalchemy.orm import Session

# # # ⚠️ PLACEHOLDER IMPORTS — replace with real function names once you show me
# # # backend/ingestion/*.py's actual contents.
# # from ingestion.incois_connector import fetch_incois_data  # noqa: F401  (guessed path/name)
# # from ingestion.sachet_connector import fetch_sachet_data  # noqa: F401  (guessed path/name)
# # from ingestion.dedup import is_duplicate  # noqa: F401  (guessed path/name)
# # from normalization.normalize import normalize_hazard_record  # noqa: F401  (guessed path/name)


# # def poll_incois(db: Session) -> int:
# #     """Fetch INCOIS hazard/tide data, dedup, normalize, persist. Returns count ingested."""
# #     raw_records = fetch_incois_data()
# #     count = 0
# #     for record in raw_records:
# #         if is_duplicate(db, record):
# #             continue
# #         normalized = normalize_hazard_record(record, source="incois")
# #         db.add(normalized)
# #         count += 1
# #     return count


# # def poll_sachet(db: Session) -> int:
# #     """Fetch SACHET CAP alert feed, dedup, normalize, persist. Returns count ingested."""
# #     raw_records = fetch_sachet_data()
# #     count = 0
# #     for record in raw_records:
# #         if is_duplicate(db, record):
# #             continue
# #         normalized = normalize_hazard_record(record, source="sachet")
# #         db.add(normalized)
# #         count += 1
# #     return count








# """
# Module 3 — ingestion_service.py (real files ke against verified)

# Flow: connector.fetch() -> ops_alert check -> dedup -> raw_storage -> normalize -> persist

# ASSUMPTION (flagged): normalization module ka function `normalize(record) -> CanonicalEvent`
# maan liya — normalization/*.py files nahi mili tune, toh ye ek cheez abhi bhi guess hai.
# Baaki sab (connectors, dedup, raw_storage, persist, config) real code se match karta hai.
# """
# from __future__ import annotations

# import logging
# import redis

# from .config import settings
# from .base_connector import BaseConnector
# from .dedup import Deduplicator
# from .raw_storage import store_raw_payload
# from .ops_alerts import check_and_alert
# from .schemas import IngestionRunResult, RawIngestRecord
# from .incois_connector import IncoisConnector
# from .sachet_connector import SachetConnector
# from .manual_connector import ManualAdminConnector
# from .persistence import persist

# from normalization.pipeline import normalize  # ASSUMPTION — confirm real path/name

# logger = logging.getLogger("ingestion.service")


# def build_connectors() -> list[BaseConnector]:
#     return [
#         IncoisConnector(settings.sources["incois"]),
#         SachetConnector(settings.sources["sachet"]),
#         # manual_admin is event-driven, not polled — excluded here
#     ]


# def run_connector(connector: BaseConnector, redis_client: redis.Redis) -> IngestionRunResult:
#     result = connector.fetch()
#     check_and_alert(connector)

#     if result.error or not result.records:
#         return result

#     dedup = Deduplicator(redis_client)
#     new_records = dedup.filter_new(result.records)

#     for record in new_records:
#         store_raw_payload(record)
#         _normalize_and_persist(record, redis_client)

#     logger.info(
#         "ingestion_service.run_complete source=%s fetched=%d new=%d",
#         connector.source.value, len(result.records), len(new_records),
#     )
#     return result


# def submit_manual_closure(connector: ManualAdminConnector, redis_client: redis.Redis, **kwargs) -> RawIngestRecord:
#     record = connector.submit_closure(**kwargs)
#     store_raw_payload(record)
#     _normalize_and_persist(record, redis_client)
#     return record


# def _normalize_and_persist(record: RawIngestRecord, redis_client: redis.Redis) -> None:
#     try:
#         event = normalize(record)
#     except Exception as exc:  # noqa: BLE001 — ek bad record se poora batch nahi girna chahiye
#         logger.warning("ingestion_service.normalize_failed source_id=%s error=%s", record.source_id, exc)
#         return
#     persist(event, redis_client)







# """
# Module 3 — ingestion_service.py

# Flow: connector.fetch() -> ops_alert check -> dedup -> raw_storage -> normalize -> persist

# ASSUMPTION (flagged): normalization module ka function `normalize(record) -> CanonicalEvent`
# maan liya gaya hai — real normalization/*.py files verify nahi hui, function name guessed.
# Baaki sab (connectors, dedup, raw_storage, persist, config) real code se match karta hai.
# """
# from __future__ import annotations

# import logging
# import redis

# from ingestion.config import settings
# from ingestion.base_connector import BaseConnector
# from ingestion.dedup import Deduplicator
# from ingestion.raw_storage import store_raw_payload
# from ingestion.ops_alerts import check_and_alert
# from ingestion.schemas import IngestionRunResult, RawIngestRecord
# from ingestion.incois_connector import IncoisConnector
# from ingestion.sachet_connector import SachetConnector
# from ingestion.manual_connector import ManualAdminConnector
# from ingestion.persistence import persist

# from normalization.normalizer import NormalizationEngine
# _normalizer = NormalizationEngine()

# logger = logging.getLogger("ingestion.service")


# def build_connectors() -> list[BaseConnector]:
#     return [
#         IncoisConnector(settings.sources["incois"]),
#         SachetConnector(settings.sources["sachet"]),
#         # manual_admin is event-driven, not polled — excluded here
#     ]


# def run_connector(connector: BaseConnector, redis_client: redis.Redis) -> IngestionRunResult:
#     result = connector.fetch()
#     check_and_alert(connector)

#     if result.error or not result.records:
#         return result

#     dedup = Deduplicator(redis_client)
#     new_records = dedup.filter_new(result.records)

#     for record in new_records:
#         store_raw_payload(record)
#         _normalize_and_persist(record, redis_client)

#     logger.info(
#         "ingestion_service.run_complete source=%s fetched=%d new=%d",
#         connector.source.value, len(result.records), len(new_records),
#     )
#     return result


# def submit_manual_closure(connector: ManualAdminConnector, redis_client: redis.Redis, **kwargs) -> RawIngestRecord:
#     record = connector.submit_closure(**kwargs)
#     store_raw_payload(record)
#     _normalize_and_persist(record, redis_client)
#     return record


# def _normalize_and_persist(record: RawIngestRecord, redis_client: redis.Redis) -> None:
#     try:
#         event = _normalizer.normalize(record)
#     except Exception as exc:  # noqa: BLE001 — ek bad record se poora batch nahi girna chahiye
#         logger.warning("ingestion_service.normalize_failed source_id=%s error=%s", record.source_id, exc)
#         return
#     persist(event, redis_client)






"""
Module 3 — ingestion_service.py

Flow: connector.fetch() -> ops_alert check -> dedup -> raw_storage -> normalize -> persist

FIXED 2026-08-13 — two real bugs found while wiring real SACHET data:
1. Dedup was marking a record "seen" the moment it was CHECKED (before persist
   was attempted). If persist then failed, the record was permanently lost —
   dedup refused to let it through again even though it was never actually
   saved. Fixed: dedup.mark_seen() is now called only AFTER a confirmed
   successful persist (see Deduplicator in ingestion/dedup.py — also updated).
2. _normalize_and_persist() had no try/except around persist() itself, so one
   bad record's DB error crashed the entire HTTP request instead of being
   logged and skipped like normalize() already correctly did.

ASSUMPTION (flagged): normalization module ka function `normalize(record) -> CanonicalEvent`
maan liya gaya hai — real normalization/*.py files verify nahi hui, function name guessed.
Baaki sab (connectors, dedup, raw_storage, persist, config) real code se match karta hai.
"""
from __future__ import annotations

import logging
import redis

from ingestion.config import settings
from ingestion.base_connector import BaseConnector
from ingestion.dedup import Deduplicator
from ingestion.raw_storage import store_raw_payload
from ingestion.ops_alerts import check_and_alert
from ingestion.schemas import IngestionRunResult, RawIngestRecord
from ingestion.incois_connector import IncoisConnector
from ingestion.sachet_connector import SachetConnector
from ingestion.manual_connector import ManualAdminConnector
from ingestion.persistence import persist

from normalization.normalizer import NormalizationEngine
_normalizer = NormalizationEngine()

logger = logging.getLogger("ingestion.service")


def build_connectors() -> list[BaseConnector]:
    return [
        # INCOIS connector disabled — placeholder/stub, INCOIS_BASE_URL never configured
        SachetConnector(settings.sources["sachet"]),
        # manual_admin is event-driven, not polled — excluded here
    ]


def run_connector(connector: BaseConnector, redis_client: redis.Redis) -> IngestionRunResult:
    result = connector.fetch()
    check_and_alert(connector)

    if result.error or not result.records:
        return result

    dedup = Deduplicator(redis_client)
    new_records = dedup.filter_new(result.records)

    persisted_count = 0
    for record in new_records:
        store_raw_payload(record)
        if _normalize_and_persist(record, redis_client):
            dedup.mark_seen(record)  # only mark seen once it's actually saved
            persisted_count += 1

    logger.info(
        "ingestion_service.run_complete source=%s fetched=%d new=%d persisted=%d",
        connector.source.value, len(result.records), len(new_records), persisted_count,
    )
    return result


def submit_manual_closure(connector: ManualAdminConnector, redis_client: redis.Redis, **kwargs) -> RawIngestRecord:
    record = connector.submit_closure(**kwargs)
    store_raw_payload(record)
    _normalize_and_persist(record, redis_client)
    return record


def _normalize_and_persist(record: RawIngestRecord, redis_client: redis.Redis) -> bool:
    """Returns True only if the record was actually normalized AND persisted
    to the DB successfully. Returning False means the record was dropped —
    either rejected by the normalizer or failed at the DB layer — and dedup
    must NOT mark it as seen, so a future run can retry it."""
    try:
        event = _normalizer.normalize(record)
    except Exception as exc:  # noqa: BLE001 — ek bad record se poora batch nahi girna chahiye
        logger.warning("ingestion_service.normalize_failed source_id=%s error=%s", record.source_id, exc)
        return False

    if event is None:
        # normalizer's own contract: None = deliberately rejected malformed alert
        logger.warning("ingestion_service.normalize_rejected source_id=%s", record.source_id)
        return False

    try:
        persist(event, redis_client)
        return True
    except Exception as exc:  # noqa: BLE001 — ek record ka DB error poore batch/request ko crash nahi karna chahiye
        logger.warning("ingestion_service.persist_failed source_id=%s error=%s", record.source_id, exc)
        return False
