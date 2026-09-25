"""
Shared pytest configuration for the budget service test suite.

Uses an in-memory SQLite engine (StaticPool) bound only to this service's
budget_* tables, and overrides the FastAPI get_db dependency. Nothing here
touches the real shared PostgreSQL database.
"""

import os

os.environ.setdefault("LLM_PROVIDER", "mock")  # deterministic tests; no live Gemini

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # registers budget_usage_records / budget_affiliate_clicks
from app.core.db import Base

from app.main import app
from app.api.dependencies import get_db

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# SQLite needs explicit FK off; no FKs defined, but keep pragma consistent.
@event.listens_for(_TEST_ENGINE, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=OFF")
    cur.close()


_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)

_TABLE_NAMES = ["budget_usage_records", "budget_affiliate_clicks"]
Base.metadata.create_all(bind=_TEST_ENGINE)


def _test_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _test_db


@pytest.fixture(autouse=True)
def _wipe_rows():
    with _TEST_ENGINE.begin() as conn:
        for name in _TABLE_NAMES:
            conn.execute(text(f"DELETE FROM {name}"))
    yield


@pytest.fixture
def db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Inter-agent service-token header (quota/IDOR-bypassing principal)."""
    from app.core.config import get_settings

    s = get_settings()
    return {"Authorization": f"Bearer {s.AGENT_SERVICE_TOKEN}"}


@pytest.fixture
def user_headers():
    """A real user JWT (Agent 1-compatible), sub='42'."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(42)}"}
