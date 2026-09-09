# """
# app/workers/celery_app.py â€” single Celery app shared by api/worker/beat containers
# (docker-compose.yml builds them all from the same image, different CMD).
# Queue names here must match the `-Q` flags in deploy/docker-compose.yml.
# """

# from celery import Celery
# from app.core.config import settings

# celery_app = Celery(
#     "coastal_safety",
#     broker=settings.REDIS_URL,
#     backend=settings.REDIS_URL,
#     include=[
#         "app.workers.ingestion_worker",
#         "app.workers.risk_worker",
#         "app.workers.notification_worker",
#         "app.workers.escalation_worker",
#         "app.workers.forecast_worker",
#         "app.workers.cleanup_worker",
#     ],
# )

# celery_app.conf.task_routes = {
#     "workers.ingestion.*": {"queue": "ingestion"},
#     "workers.risk.*": {"queue": "risk"},
#     "workers.notification.*": {"queue": "notification"},
#     "workers.escalation.*": {"queue": "escalation"},
#     "workers.forecast.*": {"queue": "forecast"},
# }

# celery_app.conf.beat_schedule = {
#     "poll-hazard-sources": {
#         "task": "workers.ingestion.poll_sources",
#         "schedule": 60.0,
#     },
#     "recompute-risk-scores": {
#         "task": "workers.risk.recompute_all",
#         "schedule": 120.0,
#     },
#     "flush-notification-queue": {
#         "task": "workers.notification.flush_queue",
#         "schedule": 10.0,
#     },
#     # Module 27 wiring: ack-timer polling, must stay below ACK_TIMEOUT_SECONDS (90s).
#     "check-ack-timeouts": {
#         "task": "workers.escalation.check_ack_timeouts",
#         "schedule": 15.0,
#     },
#     "cleanup-expired-cache": {
#         "task": "workers.cleanup.prune_expired",
#         "schedule": 3600.0,
#     },
#     "sync-beach-forecasts": {
#     "task": "workers.forecast.sync_forecasts",
#     "schedule": 21600.0,   # 6 hours — confirm karo, ye final nahi
#     },
# }

# celery_app.conf.task_acks_late = True
# celery_app.conf.worker_prefetch_multiplier = 1
# celery_app.conf.timezone = "UTC"








"""
app/workers/celery_app.py — single Celery app shared by api/worker/beat containers
(docker-compose.yml builds them all from the same image, different CMD).
Queue names here must match the `-Q` flags in deploy/docker-compose.yml.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "coastal_safety",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.ingestion_worker",
        "app.workers.risk_worker",
        "app.workers.notification_worker",
        "app.workers.escalation_worker",
        "app.workers.forecast_worker",
        "app.workers.cleanup_worker",
    ],
)

celery_app.conf.task_routes = {
    "workers.ingestion.*": {"queue": "ingestion"},
    "workers.risk.*": {"queue": "risk"},
    "workers.notification.*": {"queue": "notification"},
    "workers.escalation.*": {"queue": "escalation"},
    "workers.cleanup.*": {"queue": "cleanup"},
    "workers.forecast.*": {"queue": "risk"},
}

celery_app.conf.beat_schedule = {
    "poll-hazard-sources": {
        "task": "workers.ingestion.poll_sources",
        "schedule": 60.0,
    },
    "recompute-risk-scores": {
        "task": "workers.risk.recompute_all",
        "schedule": 120.0,
    },
    "flush-notification-queue": {
        "task": "workers.notification.flush_queue",
        "schedule": 10.0,
    },
    # Module 27 wiring: ack-timer polling, must stay below ACK_TIMEOUT_SECONDS (90s).
    "check-ack-timeouts": {
        "task": "workers.escalation.check_ack_timeouts",
        "schedule": 15.0,
    },
    "cleanup-expired-cache": {
        "task": "workers.cleanup.prune_expired",
        "schedule": 3600.0,
    },
    "sync-beach-forecasts": {
        "task": "workers.forecast.sync_forecasts",
        "schedule": 21600.0,  # 6 hours
    },
}

celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.timezone = "UTC"