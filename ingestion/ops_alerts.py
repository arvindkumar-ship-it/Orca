"""
Module 3 — Data Ingestion : Ops alerting (step 14)

If a source connector fails repeatedly, ops must know immediately — a silent
INCOIS/SACHET outage means beach verdicts and hazard warnings silently go
stale, which is exactly the "notification aggregator that doesn't actually
do anything" failure mode Module 0 explicitly forbids.
"""
from __future__ import annotations

import logging

import httpx

from .base_connector import BaseConnector
from .config import settings

logger = logging.getLogger("ingestion.ops_alerts")


def check_and_alert(connector: BaseConnector) -> None:
    if not connector.should_alert_ops():
        return

    message = (
        f"[INGESTION OUTAGE] source={connector.source.value} "
        f"consecutive_failures={connector._consecutive_failures} — "
        f"downstream risk scores for this source may be going stale."
    )
    logger.critical(message)

    if not settings.ops_alert_webhook_url:
        logger.warning("ops_alert_webhook_url not configured — alert only logged, not delivered")
        return

    try:
        httpx.post(settings.ops_alert_webhook_url, json={"text": message}, timeout=5)
    except httpx.HTTPError as exc:
        # Never let ops-alerting itself take down the ingestion worker.
        logger.error("ops_alerts.delivery_failed error=%s", exc)
