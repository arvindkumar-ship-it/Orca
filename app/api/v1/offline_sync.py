# # MODULE 16: Offline-First Engineering — API Router
# # Mounted at /v1/sync — matches project-wide "/v1/..." convention (no "/api" prefix,
# # per Module 20-26: POST /v1/trips, POST /v1/sos).

# from fastapi import APIRouter, Depends, Header, HTTPException
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.db import get_db
# from app.core.security import get_current_user
# from app.schemas.offline_sync import (
#     SyncBundleQuery,
#     SyncBundleResponse,
#     OfflineSosSyncRequest,
#     OfflineSosSyncResponse,
# )
# from app.services.offline_sync_service import build_sync_bundle, sync_offline_sos_queue

# router = APIRouter(prefix="/v1/sync", tags=["sync"])


# @router.get("/bundle", response_model=SyncBundleResponse)
# async def get_sync_bundle(
#     beach_ids: str = "",
#     last_synced_at: str | None = None,
#     x_device_id: str = Header(...),
#     user=Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     q = SyncBundleQuery(
#         beach_ids=[b for b in beach_ids.split(",") if b],
#         last_synced_at=last_synced_at,
#         device_id=x_device_id,
#     )
#     return await build_sync_bundle(db, q)


# # Called immediately on reconnect, before anything else, so queued SOS never sits idle.
# @router.post("/sos-queue", response_model=OfflineSosSyncResponse)
# async def post_offline_sos_sync(
#     body: OfflineSosSyncRequest,
#     user=Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     if len(body.packets) == 0:
#         return OfflineSosSyncResponse(results=[])
#     if len(body.packets) > 50:
#         raise HTTPException(status_code=400, detail="batch too large, max 50 packets per sync")

#     return await sync_offline_sos_queue(db, body)


# MODULE 16: Offline-First Engineering — API Router
# Mounted at /v1/sync — matches project-wide "/v1/..." convention (no "/api" prefix,
# per Module 20-26: POST /v1/trips, POST /v1/sos).
# Converted sync (B1) — was AsyncSession, project-wide decision is sync SQLAlchemy.

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.offline_sync import (
    SyncBundleQuery,
    SyncBundleResponse,
    OfflineSosSyncRequest,
    OfflineSosSyncResponse,
)
from app.services.offline_sync_service import build_sync_bundle, sync_offline_sos_queue

router = APIRouter(prefix="/v1/sync", tags=["sync"])


@router.get("/bundle", response_model=SyncBundleResponse)
def get_sync_bundle(
    beach_ids: str = "",
    last_synced_at: str | None = None,
    x_device_id: str = Header(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = SyncBundleQuery(
        beach_ids=[b for b in beach_ids.split(",") if b],
        last_synced_at=last_synced_at,
        device_id=x_device_id,
    )
    return build_sync_bundle(db, q, str(user.id))


# Called immediately on reconnect, before anything else, so queued SOS never sits idle.
@router.post("/sos-queue", response_model=OfflineSosSyncResponse)
def post_offline_sos_sync(
    body: OfflineSosSyncRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(body.packets) == 0:
        return OfflineSosSyncResponse(results=[])
    if len(body.packets) > 50:
        raise HTTPException(status_code=400, detail="batch too large, max 50 packets per sync")

    return sync_offline_sos_queue(db, body)