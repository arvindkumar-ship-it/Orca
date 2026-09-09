# MODULE 18: Audit and Analytics — Schemas

from typing import Any, Literal, Optional

from pydantic import BaseModel


class AuditEventInput(BaseModel):
    event_type: str
    entity_type: str
    entity_id: str
    actor_type: Literal["user", "admin", "system", "worker"] = "system"
    actor_id: Optional[str] = None
    metadata: dict[str, Any] = {}


class StatusChangeInput(BaseModel):
    incident_report_id: str
    from_status: Optional[str] = None
    to_status: str
    reason: Optional[str] = None


class AckLogInput(BaseModel):
    incident_route_id: str
    ack_status: str
    ack_time: str


class MeanResponseTimeResult(BaseModel):
    window_days: int
    mean_response_time_s: float
    sample_size: int


class AlertAccuracyResult(BaseModel):
    window_days: int
    total_alerts: int
    true_positive_alerts: int
    false_positive_alerts: int
    accuracy: float
    false_positive_rate: float


class MissedWarningResult(BaseModel):
    window_days: int
    total_incidents: int
    missed_incidents: int
    missed_warning_rate: float


class ThresholdRefitRecommendation(BaseModel):
    beach_id: str
    activity_type: str
    rule_parameter: str
    current_value: Optional[float] = None
    recommended_value: float
    justification: str
    based_on_incident_count: int
