"""
app/api/health.py — liveness/readiness probe used by Docker HEALTHCHECK and
any orchestrator (k8s/ECS) liveness+readiness probes in staging/production.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


@router.get("/healthz")
def healthz():
    """Liveness — process is up. No DB call, must stay fast."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness — DB reachable. Orchestrator stops routing traffic if this fails."""
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
