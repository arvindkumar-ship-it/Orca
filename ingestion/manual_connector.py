"""
Module 3 — Data Ingestion : Manual admin connector

Unlike INCOIS/SACHET this is not polled — it's invoked directly by the admin
console API (Module 21/22-area, admin CRUD) when an operator marks a beach
closed or a no-swim zone. Included here so it shares the exact same
RawIngestRecord contract, dedup logic, and persistence path as the polled
sources — a closure is not a second-class citizen in the risk engine's eyes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .base_connector import BaseConnector
from .schemas import RawIngestRecord, RecordType, Severity, SourceSystem


class ManualAdminConnector(BaseConnector):
    source = SourceSystem.MANUAL_ADMIN

    # Not used in this connector — closures are submitted directly, not fetched.
    def _fetch_raw(self, client):  # pragma: no cover
        raise NotImplementedError("ManualAdminConnector is event-driven; use submit_closure()")

    def _parse(self, raw_payload: Any) -> list[dict]:  # pragma: no cover
        raise NotImplementedError("ManualAdminConnector is event-driven; use submit_closure()")

    def submit_closure(
        self,
        *,
        admin_user_id: str,
        beach_id: str,
        reason: str,
        severity: Severity,
        geometry: dict,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
    ) -> RawIngestRecord:
        """
        Called synchronously from the admin API handler. Returns a validated
        RawIngestRecord ready for the same normalize -> dedup -> persist path
        used by polled connectors (see workers/ingestion_worker.py).
        """
        now = datetime.now(timezone.utc)
        return RawIngestRecord(
            source=SourceSystem.MANUAL_ADMIN,
            source_id=f"manual:{beach_id}:{now.isoformat()}",
            type=RecordType.LOCAL_CLOSURE,
            severity=severity,
            geometry=geometry,
            start_time=valid_from or now,
            end_time=valid_to,
            raw_json={
                "admin_user_id": admin_user_id,
                "beach_id": beach_id,
                "reason": reason,
                "submitted_at": now.isoformat(),
            },
            parsed_fields={
                "event_type": "beach closure",
                "beach_id": beach_id,
                "reason": reason,
                "hard_override_flag": True,  # manual closures always hard-override (Module 5 rule)
                "submitted_by": admin_user_id,
            },
            source_confidence=1.0,  # human-confirmed, full trust
        )
