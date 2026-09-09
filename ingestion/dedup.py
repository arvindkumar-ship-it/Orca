# """
# Module 3 — Data Ingestion : Deduplication (step 8)

# Dedup by source + alert ID + valid time window. Uses a Redis SETNX-style
# check with TTL so re-polling the same feed doesn't re-write unchanged
# records, while still allowing genuinely updated versions of the same alert
# (e.g. SACHET re-issuing with a new expiry) to pass through.
# """
# from __future__ import annotations

# import logging

# import redis

# from .schemas import RawIngestRecord

# logger = logging.getLogger("ingestion.dedup")

# # One dedup key expires slightly after its own validity window would matter,
# # so a genuinely re-issued alert with the same id+window doesn't get stuck.
# _DEDUP_TTL_SECONDS = 24 * 3600


# class Deduplicator:
#     def __init__(self, redis_client: redis.Redis):
#         self._redis = redis_client

#     def is_duplicate(self, record: RawIngestRecord) -> bool:
#         key = f"ingest:dedup:{record.dedup_key()}"
#         # SET ... NX returns True only if the key did not already exist
#         was_set = self._redis.set(key, "1", ex=_DEDUP_TTL_SECONDS, nx=True)
#         is_dup = not was_set
#         if is_dup:
#             logger.debug("dedup.skip key=%s", key)
#         return is_dup

#     def filter_new(self, records: list[RawIngestRecord]) -> list[RawIngestRecord]:
#         return [r for r in records if not self.is_duplicate(r)]


"""
Module 3 — Data Ingestion : Deduplication (step 8)

FIXED — the original marked a record "seen" via SETNX the moment it was
CHECKED, before persist was attempted. If persist then failed (e.g. the
earlier Point-vs-MultiPolygon geometry bug), the record was permanently
lost — dedup would refuse to let it through again even though it was never
actually saved. Fixed by splitting into a read-only check (is_duplicate)
and an explicit mark_seen() that the caller only invokes AFTER a
successful DB persist.
"""
from __future__ import annotations

import logging

import redis

from .schemas import RawIngestRecord

logger = logging.getLogger("ingestion.dedup")

_DEDUP_TTL_SECONDS = 24 * 3600


class Deduplicator:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    def is_duplicate(self, record: RawIngestRecord) -> bool:
        key = f"ingest:dedup:{record.dedup_key()}"
        return bool(self._redis.exists(key))

    def mark_seen(self, record: RawIngestRecord) -> None:
        key = f"ingest:dedup:{record.dedup_key()}"
        self._redis.set(key, "1", ex=_DEDUP_TTL_SECONDS)

    def filter_new(self, records: list[RawIngestRecord]) -> list[RawIngestRecord]:
        return [r for r in records if not self.is_duplicate(r)]