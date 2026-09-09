# # MODULE 18: Audit and Analytics — API Router
# # Mounted at /v1/admin/analytics. Read-only, ops-or-above.

# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.db import get_db
# from app.core.security import get_current_admin
# from app.schemas.audit import (
#     MeanResponseTimeResult,
#     AlertAccuracyResult,
#     MissedWarningResult,
#     ThresholdRefitRecommendation,
# )
# from app.services import audit_service as svc

# router = APIRouter(
#     prefix="/v1/admin/analytics", tags=["analytics"], dependencies=[Depends(get_current_admin)]
# )


# @router.get("/response-time", response_model=MeanResponseTimeResult)
# async def get_mean_response_time(window_days: int = 30, db: AsyncSession = Depends(get_db)):
#     return await svc.compute_mean_response_time(db, window_days)


# @router.get("/alert-accuracy", response_model=AlertAccuracyResult)
# async def get_alert_accuracy(window_days: int = 30, db: AsyncSession = Depends(get_db)):
#     return await svc.compute_alert_accuracy(db, window_days)


# @router.get("/missed-warnings", response_model=MissedWarningResult)
# async def get_missed_warning_rate(window_days: int = 30, db: AsyncSession = Depends(get_db)):
#     return await svc.compute_missed_warning_rate(db, window_days)


# @router.get("/threshold-recommendations", response_model=list[ThresholdRefitRecommendation])
# async def get_threshold_refit_recommendations(
#     window_days: int = 30, db: AsyncSession = Depends(get_db)
# ):
#     return await svc.generate_threshold_refit_recommendations(db, window_days)



# MODULE 18: Audit and Analytics — API Router
# Mounted at /v1/admin/analytics. Read-only, ops-or-above.
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_admin
from app.schemas.audit import (
    MeanResponseTimeResult,
    AlertAccuracyResult,
    MissedWarningResult,
    ThresholdRefitRecommendation,
)
from app.services import audit_service as svc

router = APIRouter(
    prefix="/v1/admin/analytics", tags=["analytics"], dependencies=[Depends(get_current_admin)]
)


@router.get("/response-time", response_model=MeanResponseTimeResult)
def get_mean_response_time(window_days: int = 30, db: Session = Depends(get_db)):
    return svc.compute_mean_response_time(db, window_days)


@router.get("/alert-accuracy", response_model=AlertAccuracyResult)
def get_alert_accuracy(window_days: int = 30, db: Session = Depends(get_db)):
    return svc.compute_alert_accuracy(db, window_days)


@router.get("/missed-warnings", response_model=MissedWarningResult)
def get_missed_warning_rate(window_days: int = 30, db: Session = Depends(get_db)):
    return svc.compute_missed_warning_rate(db, window_days)


@router.get("/threshold-recommendations", response_model=list[ThresholdRefitRecommendation])
def get_threshold_refit_recommendations(
    window_days: int = 30, db: Session = Depends(get_db)
):
    return svc.generate_threshold_refit_recommendations(db, window_days)