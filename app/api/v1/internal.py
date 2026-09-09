# """Module 25 — internal endpoints. Never exposed to end users; guarded by shared-secret header,
# not user JWT. Assumes app.core.security.verify_internal_key exists (Header check)."""
# from fastapi import APIRouter, Depends, Body
# from sqlalchemy.orm import Session

# from app.core.db import get_db
# from app.core.security import verify_internal_key
# from app.schemas.internal import (
#     IngestResponse, RiskRecomputeRequest, RiskRecomputeResponse, EscalateRequest, EscalateResponse,
# )
# from app.services import internal_service as svc

# router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_internal_key)])


# @router.post("/ingest/incois", response_model=IngestResponse)
# def ingest_incois(raw: dict = Body(...), db: Session = Depends(get_db)):
#     count = svc.handle_incois(db, raw)
#     return IngestResponse(status="ingested", records_ingested=count)


# @router.post("/ingest/sachet", response_model=IngestResponse)
# def ingest_sachet(raw: dict = Body(...), db: Session = Depends(get_db)):
#     count = svc.handle_sachet(db, raw)
#     return IngestResponse(status="ingested", records_ingested=count)


# @router.post("/recompute/risk", response_model=RiskRecomputeResponse)
# def recompute_risk(payload: RiskRecomputeRequest, db: Session = Depends(get_db)):
#     count = svc.handle_recompute(db, payload.beach_id)
#     return RiskRecomputeResponse(status="recomputed", beaches_recomputed=count)


# #@router.post("/router/escalate", response_model=EscalateResponse)
# # def router_escalate(payload: EscalateRequest, db: Session = Depends(get_db)):
# #     next_targets = svc.handle_escalate(db, payload.incident_id, payload.reason, payload.attempt)
# #     return EscalateResponse(incident_id=payload.incident_id, status="escalated", next_targets=next_targets)



"""Module 25 — internal endpoints. Never exposed to end users; guarded by shared-secret header,
not user JWT. Assumes app.core.security.verify_internal_key exists (Header check)."""
from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_internal_key
from app.schemas.internal import (
    IngestResponse, RiskRecomputeRequest, RiskRecomputeResponse, EscalateRequest, EscalateResponse,
    ForecastSyncResponse, NotificationFlushResponse, EscalationCheckResponse,
)
from app.services import internal_service as svc

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_internal_key)])


@router.post("/ingest/incois", response_model=IngestResponse)
def ingest_incois(raw: dict = Body(...), db: Session = Depends(get_db)):
    count = svc.handle_incois(db, raw)
    return IngestResponse(status="ingested", records_ingested=count)


@router.post("/ingest/sachet", response_model=IngestResponse)
def ingest_sachet(raw: dict = Body(...), db: Session = Depends(get_db)):
    count = svc.handle_sachet(db, raw)
    return IngestResponse(status="ingested", records_ingested=count)


@router.post("/recompute/risk", response_model=RiskRecomputeResponse)
def recompute_risk(payload: RiskRecomputeRequest, db: Session = Depends(get_db)):
    count = svc.handle_recompute(db, payload.beach_id)
    return RiskRecomputeResponse(status="recomputed", beaches_recomputed=count)


#@router.post("/router/escalate", response_model=EscalateResponse)
# def router_escalate(payload: EscalateRequest, db: Session = Depends(get_db)):
#     next_targets = svc.handle_escalate(db, payload.incident_id, payload.reason, payload.attempt)
#     return EscalateResponse(incident_id=payload.incident_id, status="escalated", next_targets=next_targets)


# --- Added: manual triggers for Celery-beat-only tasks. Production has no
# Background Worker service deployed (Render free tier doesn't offer one), so these
# three periodic beat jobs never run automatically. Each endpoint calls the exact
# same @shared_task function beat would have called — same logic, just triggered
# by an HTTP call instead of a timer. Guarded by the same X-Internal-Key as every
# other route on this router (see router-level dependency above). ---

@router.post("/sync/forecasts", response_model=ForecastSyncResponse)
def sync_forecasts(
    forecast_days: int = Query(7, description="How many days ahead to fetch/store forecasts for"),
    db: Session = Depends(get_db),
):
    """Manual replacement for beat's 'sync-beach-forecasts' (normally every 6h).
    Populates beach_forecasts for every active beach — required before
    /v1/beaches/{id}/risk or /v1/beaches/{id}/forecast can return anything but 404."""
    result = svc.handle_forecast_sync(db, forecast_days)
    return ForecastSyncResponse(**result)


@router.post("/notifications/flush", response_model=NotificationFlushResponse)
def flush_notifications(db: Session = Depends(get_db)):
    """Manual replacement for beat's 'flush-notification-queue' (normally every 10s).
    Drains any NotificationQueue rows stuck in status='queued' and delivers them."""
    result = svc.handle_notification_flush(db)
    return NotificationFlushResponse(**result)


@router.post("/escalation/check", response_model=EscalationCheckResponse)
def check_escalations(db: Session = Depends(get_db)):
    """Manual replacement for beat's 'check-ack-timeouts' (normally every 15s).
    Finds every incident whose ack timer is due right now and auto-transitions it
    (dispatched -> timeout -> escalated -> fallback_112), same as the automatic
    path would have. Run this periodically by hand (or hit it right after any SOS
    dispatch) since nothing is polling ack_timers in the background anymore."""
    result = svc.handle_escalation_check(db)
    return EscalationCheckResponse(**result)