"""
Shared pytest configuration for the Agent 4 decision service test suite.

Agent 4 is stateless — no database fixture needed. Tests drive the FastAPI
app through TestClient with the shared service token or an Agent 1-compatible
user JWT, exactly like production callers.
"""

import os

os.environ.setdefault("LLM_PROVIDER", "mock")  # deterministic tests; no live Gemini

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """Inter-agent service-token header."""
    from app.core.config import get_settings

    s = get_settings()
    return {"Authorization": f"Bearer {s.AGENT_SERVICE_TOKEN}"}


@pytest.fixture
def user_headers():
    """A real user JWT (Agent 1-compatible), sub='42'."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(42)}"}
