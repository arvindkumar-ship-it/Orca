# import uuid
# from typing import Any, Dict, Optional, List
# from pydantic import BaseModel


# class IngestResponse(BaseModel):
#     status: str
#     records_ingested: int


# class RiskRecomputeRequest(BaseModel):
#     beach_id: Optional[uuid.UUID] = None  # None = recompute all active beaches


# class RiskRecomputeResponse(BaseModel):
#     status: str
#     beaches_recomputed: int


# class EscalateRequest(BaseModel):
#     incident_id: uuid.UUID
#     reason: str
#     attempt: int


# class EscalateResponse(BaseModel):
#     incident_id: uuid.UUID
#     status: str
#     next_targets: List[str]


import uuid
from typing import Any, Dict, Optional, List
from pydantic import BaseModel


class IngestResponse(BaseModel):
    status: str
    records_ingested: int


class RiskRecomputeRequest(BaseModel):
    beach_id: Optional[uuid.UUID] = None  # None = recompute all active beaches


class RiskRecomputeResponse(BaseModel):
    status: str
    beaches_recomputed: int


class EscalateRequest(BaseModel):
    incident_id: uuid.UUID
    reason: str
    attempt: int


class EscalateResponse(BaseModel):
    incident_id: uuid.UUID
    status: str
    next_targets: List[str]


# --- Added: manual triggers for tasks normally run by Celery beat (worker/beat not
# deployed in production — see internal_service.handle_forecast_sync /
# handle_notification_flush / handle_escalation_check). ---

class ForecastSyncResponse(BaseModel):
    status: str
    beaches_processed: int
    total_inserted: int
    errors: Dict[str, str] = {}


class NotificationFlushResponse(BaseModel):
    status: str
    sent: int
    failed: int


class EscalationCheckResponse(BaseModel):
    status: str
    processed: int
    failed: int