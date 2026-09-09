"""Module 2 â€” Database Schema: engine + session.

FIX APPLIED: load_dotenv() with no path argument searches upward from the current
WORKING DIRECTORY (CWD), not from this file's location. Depending on where uvicorn/celery
is launched from (backend/ vs repo root vs elsewhere), it may never find wavesafe/.env â€”
this is exactly the blocker you hit. Fixed by resolving the path explicitly relative to
this file, so it works identically no matter where the process is started from.
"""
from __future__ import annotations
import os
from contextlib import contextmanager
from pathlib import Path
from dotenv import load_dotenv

# This file: backend/app/core/db.py
# parents[0]=core, [1]=app, [2]=backend, [3]=repo root (wavesafe/) â€” where .env actually lives
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import declarative_base

#Base = declarative_base()
from app.models.base import Base  # noqa: F401 -- re-exported so BOTH app.core.db.Base
# and app.models.base.Base point to the SAME SQLAlchemy registry (Bug #2 fix).

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://user:pass@localhost:5433/coastal_safety",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency â€” used via Depends(get_db) in routers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
