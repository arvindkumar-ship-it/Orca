"""
Module 4 — Normalization Engine : Normalizer

Implements the module's exact steps:
1. Map source fields to canonical fields.
2. Convert time to UTC.                          (already done in schemas.RawIngestRecord)
3. Normalize units.
4. Infer missing geometry only when source supports it.
5. Tag uncertainty when fields are incomplete.
6. Reject malformed alerts.
7. Keep both raw and parsed versions.
8. Produce event for risk engine.

Input: RawIngestRecord (Module 3's output contract)
Output: CanonicalHazardEvent | CanonicalForecastEvent | None (None = rejected)
"""
from __future__ import annotations

import logging
from typing import Optional, Union

from pydantic import ValidationError

from .canonical_schema import (
    ALL_ACTIVITY_TYPES,
    EVACUATION_ALERT_TYPES,
    HARD_OVERRIDE_ALERT_TYPES,
    CanonicalAlertType,
    CanonicalForecastEvent,
    CanonicalHazardEvent,
)
from .unit_conversion import clamp_water_quality_index

logger = logging.getLogger("normalization.normalizer")

# Import ingestion's schema types without creating a hard package-layout
# dependency — adjust this import path once Module 3/4 sit in their final
# repo location (e.g. both under app/pipeline/).
try:
    from ingestion.schemas import RawIngestRecord, RecordType  # type: ignore
except ImportError:  # pragma: no cover - fallback for isolated testing
    from typing import Any as RawIngestRecord  # type: ignore
    RecordType = None  # type: ignore


_EVENT_TYPE_MAP: dict[str, CanonicalAlertType] = {
    "tsunami warning": CanonicalAlertType.TSUNAMI_WARNING,
    "storm surge warning": CanonicalAlertType.STORM_SURGE_WARNING,
    "cyclone warning": CanonicalAlertType.CYCLONE_WARNING,
    "high wave warning": CanonicalAlertType.HIGH_WAVE_WARNING,
    "evacuation order": CanonicalAlertType.EVACUATION_ORDER,
    "beach closure": CanonicalAlertType.BEACH_CLOSURE,
    "coast guard closure": CanonicalAlertType.COAST_GUARD_CLOSURE,
}


class NormalizationEngine:

    def normalize(self, raw: "RawIngestRecord") -> Optional[Union[CanonicalHazardEvent, CanonicalForecastEvent]]:
        try:
            if raw.type.value == "hazard_warning" or raw.type.value == "local_closure":
                return self._normalize_hazard(raw)
            if raw.type.value == "ocean_forecast":
                return self._normalize_forecast(raw)
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            # Step 6: reject malformed alerts rather than propagate a bad record.
            logger.warning(
                "normalizer.reject source=%s source_id=%s error=%s",
                raw.source.value, raw.source_id, exc,
            )
            return None

        logger.warning("normalizer.unknown_type source=%s type=%s", raw.source.value, raw.type)
        return None

    # ---- hazard warnings & local closures ----
    def _normalize_hazard(self, raw: "RawIngestRecord") -> CanonicalHazardEvent:
        parsed = raw.parsed_fields
        event_type_raw = (parsed.get("event_type") or "").strip().lower()
        alert_type = _EVENT_TYPE_MAP.get(event_type_raw, CanonicalAlertType.OTHER)

        uncertainty: list[str] = list(parsed.get("_missing_fields", []))

        geometry = raw.geometry.model_dump() if raw.geometry else None
        if geometry is None:
            uncertainty.append("geometry")
            # Step 4: infer missing geometry ONLY when the source supports it.
            # Manual admin closures always carry a beach_id we can resolve to
            # the beach's stored polygon at persistence time; other sources
            # get no inferred geometry — an alert with unknown area must not
            # silently default to "affects everywhere" or "affects nowhere".

        hard_override = bool(parsed.get("hard_override_flag", False)) or alert_type in HARD_OVERRIDE_ALERT_TYPES
        evacuation = alert_type in EVACUATION_ALERT_TYPES

        return CanonicalHazardEvent(
            source_system=raw.source.value,
            source_alert_id=raw.source_id,
            alert_type=alert_type,
            severity=(raw.severity.value if raw.severity else "moderate"),
            title=parsed.get("headline"),
            description=parsed.get("description") or parsed.get("reason"),
            geometry=geometry,
            issued_at=raw.start_time or raw.ingest_time,
            valid_from=raw.start_time,
            valid_to=raw.end_time,
            eta_minutes=parsed.get("eta_minutes"),
            hard_override_flag=hard_override,
            evacuation_flag=evacuation,
            affected_activity_types=sorted(ALL_ACTIVITY_TYPES),  # step 1 default; refine per-source if source scopes it
            confidence=raw.source_confidence,
            uncertainty_flags=uncertainty,
            raw_payload=raw.raw_json,
        )

    # ---- ocean forecast observations ----
    def _normalize_forecast(self, raw: "RawIngestRecord") -> CanonicalForecastEvent:
        parsed = raw.parsed_fields
        uncertainty: list[str] = list(parsed.get("_missing_fields", []))

        if raw.geometry is None:
            uncertainty.append("geometry")
            # Step 4: forecasts without geometry cannot be matched to a beach
            # by nearest-station logic — persistence layer must handle this
            # (skip + log, do not guess a beach_id).

        return CanonicalForecastEvent(
            beach_id=None,  # resolved downstream by nearest-station match against `beaches`
            station_source_id=str(parsed.get("station_id", raw.source_id)),
            forecast_time=raw.start_time or raw.ingest_time,
            wave_height=parsed.get("wave_height"),
            current_speed=parsed.get("current_speed"),
            wind_speed=parsed.get("wind_speed"),
            swell_height=parsed.get("swell_height"),
            tide_state=parsed.get("tide_state"),
            rainfall=parsed.get("rainfall"),
            visibility=parsed.get("visibility"),
            water_quality=clamp_water_quality_index(parsed.get("water_quality")),
            source=raw.source.value,
            confidence=raw.source_confidence,
            uncertainty_flags=uncertainty,
            raw_payload=raw.raw_json,
        )
