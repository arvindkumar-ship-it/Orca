"""
Module 3 — Data Ingestion : Base connector

Shared behavior every source adapter (INCOIS, SACHET, manual admin) inherits:
- timeout + retry with exponential backoff (steps 2, 3)
- reject invalid/malformed records instead of raising and killing the whole batch (step 10)
- mark missing values instead of guessing them (step 11)
- record ingestion latency (step 13)
- surface failures for ops alerting (step 14) without crashing the scheduler
"""
from __future__ import annotations

import abc
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from .config import SourceConfig
from .schemas import IngestionRunResult, RawIngestRecord, SourceSystem

logger = logging.getLogger("ingestion.connector")


class ConnectorError(Exception):
    """Raised when a source is unreachable or returns unusable data after all retries."""


class BaseConnector(abc.ABC):
    source: SourceSystem

    def __init__(self, config: SourceConfig):
        self.config = config
        self._consecutive_failures = 0

    # ---- override in each connector ----
    @abc.abstractmethod
    def _fetch_raw(self, client: httpx.Client) -> Any:
        """Hit the source endpoint and return the raw (unvalidated) payload."""
        raise NotImplementedError

    @abc.abstractmethod
    def _parse(self, raw_payload: Any) -> list[dict]:
        """
        Turn the raw payload into a list of dicts, each shaped closely enough
        to build a RawIngestRecord. Source-specific parsing lives here only —
        no business logic, no normalization (that's Module 4).
        """
        raise NotImplementedError

    # ---- shared machinery ----
    def fetch(self) -> IngestionRunResult:
        started = time.monotonic()
        fetched_at = datetime.now(timezone.utc)
        records: list[RawIngestRecord] = []
        rejected = 0
        error: str | None = None

        try:
            raw_payload = self._fetch_with_retry()
            parsed_items = self._parse(raw_payload)
            for item in parsed_items:
                rec = self._safe_build_record(item)
                if rec is not None:
                    records.append(rec)
                else:
                    rejected += 1
            self._consecutive_failures = 0
        except ConnectorError as exc:
            self._consecutive_failures += 1
            error = str(exc)
            logger.error(
                "connector.fetch_failed source=%s consecutive_failures=%d error=%s",
                self.source.value, self._consecutive_failures, error,
            )

        duration_ms = (time.monotonic() - started) * 1000
        result = IngestionRunResult(
            source=self.source,
            records=records,
            fetched_at=fetched_at,
            duration_ms=duration_ms,
            rejected_count=rejected,
            error=error,
        )
        logger.info(
            "connector.fetch_complete source=%s records=%d rejected=%d duration_ms=%.1f error=%s",
            self.source.value, len(records), rejected, duration_ms, error,
        )
        return result

    def should_alert_ops(self) -> bool:
        from .config import settings
        return self._consecutive_failures >= settings.ops_alert_min_consecutive_failures

    def _fetch_with_retry(self) -> Any:
        last_exc: Exception | None = None
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            for attempt in range(1, self.config.max_retries + 1):
                try:
                    return self._fetch_raw(client)
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    wait = self.config.backoff_base_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "connector.retry source=%s attempt=%d/%d wait=%.1fs error=%s",
                        self.source.value, attempt, self.config.max_retries, wait, exc,
                    )
                    if attempt < self.config.max_retries:
                        time.sleep(wait)
        raise ConnectorError(f"{self.source.value} unreachable after {self.config.max_retries} attempts: {last_exc}")

    def _safe_build_record(self, item: dict) -> RawIngestRecord | None:
        """Reject malformed items instead of blowing up the whole ingest run (step 10)."""
        try:
            item = self._mark_missing_values(item)
            return RawIngestRecord(**item)
        except ValidationError as exc:
            logger.warning(
                "connector.record_rejected source=%s source_id=%s error=%s",
                self.source.value, item.get("source_id", "unknown"), exc,
            )
            return None

    @staticmethod
    def _mark_missing_values(item: dict) -> dict:
        """Step 11: mark missing values explicitly rather than silently dropping fields."""
        parsed = item.get("parsed_fields", {}) or {}
        missing = [k for k, v in parsed.items() if v is None]
        if missing:
            parsed["_missing_fields"] = missing
        item["parsed_fields"] = parsed
        return item
