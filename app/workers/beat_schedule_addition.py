"""
Add this entry to Module 26's existing Celery Beat schedule dict
(app/workers/celery_app.py or wherever beat_schedule is defined).
Poll interval must stay below ACK_TIMEOUT_SECONDS (90s) so no timer
fires late by more than one tick — use 15s.
"""
from celery.schedules import crontab  # noqa: F401  (kept for parity with other entries)

ESCALATION_BEAT_ENTRY = {
    "check-ack-timeouts": {
        "task": "workers.escalation.check_ack_timeouts",
        "schedule": 15.0,  # seconds
    }
}
