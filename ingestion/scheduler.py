"""
Module 3 — Data Ingestion : Scheduler (step 3)

Lightweight in-process scheduler abstraction. In production this is driven
by Celery beat (see workers/ingestion_worker.py for the actual periodic
task registration) — this class exists so the polling-interval logic is
testable independent of Celery.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .base_connector import BaseConnector
from .config import IngestionSettings

logger = logging.getLogger("ingestion.scheduler")


@dataclass
class ScheduledConnector:
    connector: BaseConnector
    last_run_monotonic: float = 0.0

    def is_due(self, now: float) -> bool:
        interval = self.connector.config.poll_interval_seconds
        if interval <= 0:
            return False  # event-driven connectors (manual_admin) are never polled
        return (now - self.last_run_monotonic) >= interval


class IngestionScheduler:
    """
    Call `.tick()` on a fixed short interval (e.g. every 10s from a Celery
    beat task or a simple loop) — it runs only the connectors that are due,
    each on its own configured poll_interval_seconds.
    """

    def __init__(self, connectors: list[BaseConnector]):
        self._scheduled = [ScheduledConnector(connector=c) for c in connectors]

    def tick(self, on_result) -> None:
        now = time.monotonic()
        for sc in self._scheduled:
            if sc.is_due(now):
                logger.info("scheduler.run source=%s", sc.connector.source.value)
                result = sc.connector.fetch()
                sc.last_run_monotonic = now
                on_result(result, sc.connector)

    def run_forever(self, on_result, tick_seconds: int = 10) -> None:  # pragma: no cover
        logger.info("scheduler.starting tick_seconds=%d", tick_seconds)
        while True:
            self.tick(on_result)
            time.sleep(tick_seconds)
