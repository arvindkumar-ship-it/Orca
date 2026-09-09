"""
app/core/cache.py

Redis-backed cache helpers for the risk engine (Module 5) and forecast engine (Module 6),
which per their own comments cache computed risk/forecast values in Redis rather than
recomputing on every request.

⚠️ ASSUMPTION — risk_engine/ and forecast_engine/ (Module 5 & 6 zips) were not available to
verify their exact key-naming convention. The functions below (`get_json`, `set_json`,
`prune_expired`) follow the naming convention implied by cleanup_worker.py's comment
("Redis risk/forecast cache (Module 5 step 10)") and its confirmed call:

    from app.core.cache import prune_expired
    ...
    pruned = prune_expired()   # called with zero args, returns an int count

If risk_engine/engine.py or forecast_engine/*.py use a different key prefix than
"risk:*" / "forecast:*", update RISK_PREFIX / FORECAST_PREFIX below to match — everything
else in this file is prefix-agnostic.
"""
import json
from typing import Any, Optional

from app.redis_client import redis_client

RISK_PREFIX = "risk:"
FORECAST_PREFIX = "forecast:"


def get_json(key: str) -> Optional[Any]:
    raw = redis_client.get(key)
    return json.loads(raw) if raw is not None else None


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    redis_client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


def prune_expired() -> int:
    """Redis TTL keys expire on their own — this exists as a defensive sweep for any
    risk:*/forecast:* keys that were written without a TTL (a bug elsewhere) so they
    don't accumulate forever. Returns the number of keys deleted.
    Called by cleanup_worker.py's scheduled task with no arguments."""
    pruned = 0
    for prefix in (RISK_PREFIX, FORECAST_PREFIX):
        for key in redis_client.scan_iter(match=f"{prefix}*"):
            if redis_client.ttl(key) == -1:  # -1 = exists but no TTL set
                redis_client.delete(key)
                pruned += 1
    return pruned