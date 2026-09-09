import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class TripCreateRequest(BaseModel):
    beach_id: uuid.UUID
    activity_type: str
    planned_from: datetime
    planned_to: datetime

    @field_validator("planned_to")
    @classmethod
    def to_after_from(cls, v, info):
        pf = info.data.get("planned_from")
        if pf and v <= pf:
            raise ValueError("planned_to must be after planned_from")
        return v


class TripCreateResponse(BaseModel):
    trip_id: uuid.UUID
    status: str


class TripDetailResponse(BaseModel):
    trip_id: uuid.UUID
    beach_id: uuid.UUID
    activity_type: str
    planned_from: datetime
    planned_to: datetime
    status: str
    latest_advisory: str
    safe_window_start: Optional[datetime] = None
    safe_window_end: Optional[datetime] = None


class TripRiskExplanation(BaseModel):
    danger_slots: List[str] = Field(default_factory=list)


class TripRiskResponse(BaseModel):
    trip_id: uuid.UUID
    min_risk: float
    max_risk: float
    recommendation: str
    safe_window_start: Optional[datetime] = None
    safe_window_end: Optional[datetime] = None
    explanation: TripRiskExplanation


class TripRescanResponse(BaseModel):
    trip_id: uuid.UUID
    status: str
    risk_changed: bool


class TripCancelResponse(BaseModel):
    trip_id: uuid.UUID
    status: str
