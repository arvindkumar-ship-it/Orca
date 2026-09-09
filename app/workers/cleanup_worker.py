"""
app/workers/cleanup_worker.py
Beat calls prune_expired() hourly — clears expired cache entries / stale rows.
dedup.py already self-expires via Redis TTL, so this targets DB-side and
cache-side cleanup only.

ASSUMPTION: app.core.cache exposes prune_expired() — not verified
against real cache.py yet.
"""
from __future__ import annotations
import logging
from celery import shared_task
from app.core.cache import prune_expired as cache_prune_expired  # Bug #13 fix — was shadowed by local prune_expired() below, causing infinite self-recursion

logger = logging.getLogger(__name__)


@shared_task(name="workers.cleanup.prune_expired")
def prune_expired() -> dict:
    try:
        cache_cleared = cache_prune_expired()
        return {"cache_keys_cleared": cache_cleared}
    except Exception:
        logger.exception("cleanup_worker.prune_failed")
        raise