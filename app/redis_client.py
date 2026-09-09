"""
app/redis_client.py

Single shared Redis connection, imported wherever raw Redis access is needed (Module 3's
ingestion dedup, Module 5/6's risk & forecast caching via app.core.cache, Celery uses its
own connection internally via REDIS_URL so this is not needed by celery_app.py itself).
"""
import redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)