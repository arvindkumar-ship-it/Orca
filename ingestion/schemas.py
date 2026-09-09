"""ORCA — GENERALIZE of ingestion/schemas.py. Applies ORCA_SCHEMA_PATCH.md:
adds SourceSystem.MOSDAC_BHUVAN, RecordType.PFZ_ADVISORY/SST_RASTER/
CHLOROPHYLL_RASTER, and "LineString" to GeoJSONGeometry's allowed types.
Everything else copied verbatim from the original."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class SourceSystem(str, Enum):
    INCOIS = "incois"
    SACHET = "sachet"
    MANUAL_ADMIN = "manual_admin"
    MOSDAC_BHUVAN = "mosdac_bhuvan"


class RecordType(str, Enum):
    OCEAN_FORECAST = "ocean_forecast"
    HAZARD_WARNING = "hazard_warning"
    LOCAL_CLOSURE = "local_closure"
    PFZ_ADVISORY = "pfz_advisory"
    SST_RASTER = "sst_raster"
    CHLOROPHYLL_RASTER = "chlorophyll_raster"


class Severity(str, Enum):
    INFO = "info"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class GeoJSONGeometry(BaseModel):
    type: str  # "Point" | "Polygon" | "MultiPolygon" | "LineString"
    coordinates: Any

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        allowed = {"Point", "Polygon", "MultiPolygon", "LineString"}
        if v not in allowed:
            raise ValueError(f"geometry type must be one of {allowed}, got {v}")
        return v


class RawIngestRecord(BaseModel):
    source: SourceSystem
    source_id: str
    type: RecordType
    severity: Optional[Severity] = None
    geometry: Optional[GeoJSONGeometry] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    raw_json: dict[str, Any]
    parsed_fields: dict[str, Any] = Field(default_factory=dict)
    ingest_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_confidence: float = 1.0

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _ensure_utc(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    def dedup_key(self) -> str:
        start = self.start_time.isoformat() if self.start_time else "none"
        end = self.end_time.isoformat() if self.end_time else "none"
        return f"{self.source.value}:{self.source_id}:{start}:{end}"


class IngestionRunResult(BaseModel):
    source: SourceSystem
    records: list[RawIngestRecord]
    fetched_at: datetime
    duration_ms: float
    rejected_count: int = 0
    error: Optional[str] = None
