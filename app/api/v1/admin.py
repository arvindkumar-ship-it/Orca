# MODULE 17: Admin Console — API Router
# Mounted at /v1/admin. All routes require ops-or-above (get_current_admin); risk-rule
# tuning and log export additionally require admin role (enforced in admin_service).

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_admin
from app.schemas.admin import (
    BeachUpsertInput,
    ActivityThresholdInput,
    JurisdictionUpsertInput,
    HospitalUpsertInput,
    SafeZoneUpsertInput,
    IncidentReviewFilters,
    RiskRuleUpdateInput,
    LogExportRequest,
)
from app.services import admin_service as svc

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# Step 1-2: beaches + polygon upload
@router.post("/beaches")
def post_beach(
    body: BeachUpsertInput, admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    return svc.upsert_beach(db, admin, body)


@router.get("/beaches/{beach_id}/validate-geometry")
def get_beach_validation(beach_id: str, db: Session = Depends(get_db)):
    return svc.validate_beach_geometry(db, beach_id)


# Step 3: activity thresholds
@router.post("/activity-thresholds")
def post_activity_threshold(
    body: ActivityThresholdInput,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return svc.upsert_activity_threshold(db, admin, body)


# Step 4: jurisdictions
@router.post("/jurisdictions")
def post_jurisdiction(
    body: JurisdictionUpsertInput,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return svc.upsert_jurisdiction(db, admin, body)


# Step 5: hospitals
@router.post("/hospitals")
def post_hospital(
    body: HospitalUpsertInput, admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    return svc.upsert_hospital(db, admin, body)


@router.post("/safe-zones")
def post_safezone(
    body: SafeZoneUpsertInput, admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    return svc.upsert_safezone(db, admin, body)


# Step 6: incident review
@router.get("/incidents")
def get_incidents(
    status: str | None = None,
    incident_type: str | None = None,
    beach_id: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    filters = IncidentReviewFilters(
        status=status,
        incident_type=incident_type,
        beach_id=beach_id,
        from_=from_,
        to=to,
        page=page,
        page_size=page_size,
    )
    return svc.list_incidents(db, filters)


# Step 7: acknowledgement review
@router.get("/incidents/{incident_id}/acknowledgements")
def get_acknowledgements(incident_id: str, db: Session = Depends(get_db)):
    rows = svc.list_acknowledgements(db, incident_id)
    return {"rows": rows}


# Step 8: response latency
@router.get("/metrics/response-latency")
def get_response_latency(window_days: int = 7, db: Session = Depends(get_db)):
    return svc.get_response_latency_metrics(db, window_days)


# Step 9: risk rule tuning (admin-only, enforced in service layer)
@router.post("/risk-rules/tune")
def post_risk_rule_update(
    body: RiskRuleUpdateInput, admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    return svc.update_risk_rule(db, admin, body)


# Step 10: log export
@router.post("/logs/export")
def post_log_export(
    body: LogExportRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)
):
    output = svc.export_logs(db, admin, body)
    media_type = "text/csv" if body.format == "csv" else "application/json"
    headers = {"Content-Disposition": f'attachment; filename="{body.entity_type}_export.{body.format}"'}
    return Response(content=output, media_type=media_type, headers=headers)