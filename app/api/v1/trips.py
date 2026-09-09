"""
Module 20 — API Layer: Trip Planning.
Assumes app.core.security.get_current_user and app.core.db.get_db already exist (Modules 2A/19).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.schemas.trip import (
    TripCreateRequest, TripCreateResponse, TripDetailResponse,
    TripRiskResponse, TripRiskExplanation, TripRescanResponse, TripCancelResponse,
)
from app.services import trip_service

router = APIRouter(prefix="/v1/trips", tags=["trips"])

@router.get("", response_model=list[TripDetailResponse])
def list_trips(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.models.forecast_risk import TripPlan

    trips = (
        db.query(TripPlan)
        .filter(TripPlan.user_id == user.id)
        .order_by(TripPlan.created_at.desc())
        .all()
    )

    results = []
    for trip in trips:
        snap = trip_service.latest_snapshot(db, trip.id)
        results.append(
            TripDetailResponse(
                trip_id=trip.id,
                beach_id=trip.beach_id,
                activity_type=trip.activity_type,
                planned_from=trip.planned_from,
                planned_to=trip.planned_to,
                status=trip.status,
                latest_advisory=trip_service.advisory_label(snap),
                safe_window_start=snap.safe_window_start if snap else None,
                safe_window_end=snap.safe_window_end if snap else None,
            )
        )
    return results

def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ForbiddenError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@router.post("", response_model=TripCreateResponse, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripCreateRequest, db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    trip = _handle(
        trip_service.create_trip, db, user.id, payload.beach_id, payload.activity_type,
        payload.planned_from, payload.planned_to,
    )
    return TripCreateResponse(trip_id=trip.id, status=trip.status)


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(trip_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    trip = _handle(trip_service.get_trip, db, trip_id, user.id)
    snap = trip_service.latest_snapshot(db, trip.id)
    return TripDetailResponse(
        trip_id=trip.id,
        beach_id=trip.beach_id,
        activity_type=trip.activity_type,
        planned_from=trip.planned_from,
        planned_to=trip.planned_to,
        status=trip.status,
        latest_advisory=trip_service.advisory_label(snap),
        safe_window_start=snap.safe_window_start if snap else None,
        safe_window_end=snap.safe_window_end if snap else None,
    )


@router.get("/{trip_id}/risk", response_model=TripRiskResponse)
def get_trip_risk(trip_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    snap = _handle(trip_service.get_trip_risk, db, trip_id, user.id)
    return TripRiskResponse(
        trip_id=snap.trip_plan_id,
        min_risk=float(snap.min_risk or 0),
        max_risk=float(snap.max_risk or 0),
        recommendation=snap.recommendation,
        safe_window_start=snap.safe_window_start,
        safe_window_end=snap.safe_window_end,
        explanation=TripRiskExplanation(danger_slots=(snap.explanation or {}).get("danger_slots", [])),
    )


@router.post("/{trip_id}/rescan", response_model=TripRescanResponse)
def rescan_trip(trip_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    trip, risk_changed = _handle(trip_service.rescan_trip, db, trip_id, user.id)
    return TripRescanResponse(trip_id=trip.id, status="rescanned", risk_changed=risk_changed)


@router.post("/{trip_id}/cancel", response_model=TripCancelResponse)
def cancel_trip(trip_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    trip = _handle(trip_service.cancel_trip, db, trip_id, user.id)
    return TripCancelResponse(trip_id=trip.id, status=trip.status)
