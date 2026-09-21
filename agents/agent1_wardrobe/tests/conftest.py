"""
Shared Pytest Fixtures and Test Database Configuration.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import Base, get_db
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.models.analysis import AnalysisRecord  # noqa: F401 — register table for create_all
from app.core.security import hash_password

# Use a shared in-memory SQLite database across all test modules
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Seed demo user
    demo_u = User(name="Demo Stylist", email="demo@fashora.ai", password_hash=hash_password("password123"))
    db.add(demo_u)
    db.commit()
    db.refresh(demo_u)

    # Seed demo items for tests
    items = [
        WardrobeItem(wardrobe_code="W001", user_id=demo_u.id, image_path="uploads/seed1.png", category="top", type="blouse", colour="black", style="smart_casual", formality=0.70, confidence=0.92, attributes_confirmed=True),
        WardrobeItem(wardrobe_code="W002", user_id=demo_u.id, image_path="uploads/seed2.png", category="bottom", type="jeans", colour="blue", style="casual", formality=0.40, confidence=0.95, attributes_confirmed=True),
        WardrobeItem(wardrobe_code="W003", user_id=demo_u.id, image_path="uploads/seed3.png", category="shoes", type="loafers", colour="beige", style="smart_casual", formality=0.65, confidence=0.89, attributes_confirmed=True),
    ]
    db.add_all(items)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
