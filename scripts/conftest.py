"""
tests/conftest.py — shared fixtures. Uses a real Postgres+PostGIS test DB
(not sqlite) because incident_reports.geom is a GENERATED STORED column and
several queries use ST_* functions — sqlite can't fake that.
Set TEST_DATABASE_URL in .env.test, pointed at a disposable schema/db.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.db import get_db

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db():
    """One transaction per test, rolled back after — tests never pollute each other."""
    connection = engine.connect()
    txn = connection.begin()
    session = TestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    def _get_db_override():
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db):
    user_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO users (id, phone, name, consent_location, consent_emergency_share) "
            "VALUES (:id, :phone, 'Test User', true, true)"
        ),
        {"id": str(user_id), "phone": f"+91900000{uuid.uuid4().int % 10000:04d}"},
    )
    db.flush()
    return user_id


@pytest.fixture()
def test_beach(db):
    beach_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO beaches (id, name, state, geom, active) "
            "VALUES (:id, 'Test Beach', 'Test State', "
            "ST_GeomFromText('POLYGON((80.2 13.0,80.3 13.0,80.3 13.1,80.2 13.1,80.2 13.0))', 4326), true)"
        ),
        {"id": str(beach_id)},
    )
    db.flush()
    return beach_id


@pytest.fixture()
def make_incident(db, test_user, test_beach):
    """Factory: create an incident_report directly at a given starting status."""

    def _make(status: str = "created", incident_type: str = "panic"):
        incident_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO incident_reports "
                "(id, user_id, beach_id, incident_type, severity, lat, lng, status, trigger_type, created_at, updated_at) "
                "VALUES (:id, :uid, :bid, :itype, 'high', 13.05, 80.28, :status, 'manual_button', :now, :now)"
            ),
            {
                "id": str(incident_id),
                "uid": str(test_user),
                "bid": str(test_beach),
                "itype": incident_type,
                "status": status,
                "now": datetime.now(timezone.utc),
            },
        )
        db.flush()
        return incident_id

    return _make
