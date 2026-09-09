from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import verify_internal_key, verify_partner_key
from app.schemas.hospital_router import DispatchHospitalRequest
from app.services import hospital_router_service as service

router = APIRouter(tags=["hospital-router"])


@router.post("/internal/hospital-router/dispatch", status_code=201)
def dispatch(body: DispatchHospitalRequest, db: Session = Depends(get_db), _=Depends(verify_internal_key)):
    try:
        result = service.route_to_hospital(db, body.incident_report_id)
        if result["no_match"]:
            raise HTTPException(404, "No matching hospital found within radius")
        return result
    except ValueError:
        raise HTTPException(404, "Incident not found")


@router.post("/hospital-router/routes/{route_id}/ack")
def ack(route_id: str, db: Session = Depends(get_db), _=Depends(verify_partner_key)):
    try:
        service.acknowledge_hospital_route(db, route_id)
        return {"route_id": route_id, "status": "acknowledged"}
    except ValueError:
        raise HTTPException(404, "Route not found")
