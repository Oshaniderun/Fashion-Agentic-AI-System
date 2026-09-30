"""
Tests for Agent 2 server-side search history:
- POST /api/v1/search records a user-scoped entry (service-token calls do not)
- handoff fan-out records one entry per category
- GET/DELETE /api/v1/history[*] are private to the calling user
- detail endpoint resolves stored product IDs against the live catalogue
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

import pytest

from app.main import app
from app.api.dependencies import engine
from app.models.product import Base
from app.models.search_history import SearchHistory  # noqa: F401 (table registration)
from app.core.security import create_access_token
from app.core.config import get_settings
from app.services.retrieval_service import get_retrieval_service
from shared.constants import ProductCategory

client = TestClient(app)
settings = get_settings()


@pytest.fixture(autouse=True)
def setup_catalog_and_tables():
    Base.metadata.create_all(bind=engine)
    get_retrieval_service().products = {
        "TEST_SHOES_1": {
            "product_id": "TEST_SHOES_1",
            "product_name": "Test Loafers",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "currency": "USD",
            "availability": True,
            "store": "Amazon Fashion",
            "product_url": "https://www.amazon.com/dp/TEST_SHOES_1",
        }
    }
    yield
    with engine.begin() as conn:
        conn.execute(SearchHistory.__table__.delete())


def _user_headers(sub: str) -> dict:
    token = create_access_token(data={"sub": sub, "email": f"{sub}@example.com"})
    return {"Authorization": f"Bearer {token}"}


def _search(headers: dict, request_id: str = "req-hist-1") -> dict:
    payload = {
        "request_id": request_id,
        "required_category": ProductCategory.SHOES.value,
        "preferred_colour": "Beige",
        "query_text": "beige loafers smart casual",
        "max_price": 5000.0,
        "top_k": 5,
    }
    res = client.post("/api/v1/search", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_search_records_history_for_user():
    headers = _user_headers("9001")
    body = _search(headers)
    assert body["results"], "sanity: retrieval itself must still work"

    res = client.get("/api/v1/history", headers=headers)
    assert res.status_code == 200
    entries = res.json()["entries"]
    assert len(entries) == 1
    e = entries[0]
    assert e["source"] == "search"
    assert e["category"] == ProductCategory.SHOES.value
    assert e["status"] in {"ok", "relaxed", "low_confidence", "no_results"}
    assert e["result_count"] == len(body["results"])
    assert e["request_id"] == "req-hist-1"
    assert "TEST_SHOES_1" in e["product_ids"]


def test_service_token_search_not_recorded():
    payload = {
        "request_id": "req-svc-hist",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5,
    }
    res = client.post("/api/v1/search", json=payload, headers={"X-Service-Token": settings.SERVICE_TOKEN})
    assert res.status_code == 200

    svc_hist = client.get("/api/v1/history", headers={"X-Service-Token": settings.SERVICE_TOKEN})
    assert svc_hist.status_code == 403

    res = client.get("/api/v1/history", headers=_user_headers("9002"))
    assert res.json()["entries"] == []


def test_history_is_private_per_user():
    _search(_user_headers("9003"))
    other = _user_headers("9004")
    assert client.get("/api/v1/history", headers=other).json()["entries"] == []
    assert client.get("/api/v1/history", headers=_user_headers("9003")).json()["entries"]


def test_history_detail_resolves_products():
    headers = _user_headers("9005")
    _search(headers)
    entry = client.get("/api/v1/history", headers=headers).json()["entries"][0]

    detail = client.get(f"/api/v1/history/{entry['id']}", headers=headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["products"][0]["product_id"] == "TEST_SHOES_1"
    assert d["products"][0]["product_name"] == "Test Loafers"
    assert "product_ids" not in d

    # another user cannot read it
    assert client.get(f"/api/v1/history/{entry['id']}", headers=_user_headers("9006")).status_code == 404


def test_delete_and_clear():
    headers = _user_headers("9007")
    _search(headers, "req-a")
    _search(headers, "req-b")
    entries = client.get("/api/v1/history", headers=headers).json()["entries"]
    assert len(entries) == 2

    res = client.delete(f"/api/v1/history/{entries[0]['id']}", headers=headers)
    assert res.status_code == 200
    assert len(client.get("/api/v1/history", headers=headers).json()["entries"]) == 1

    res = client.delete("/api/v1/history", headers=headers)
    assert res.json()["deleted"] == 1
    assert client.get("/api/v1/history", headers=headers).json()["entries"] == []

    assert client.delete(f"/api/v1/history/{entries[0]['id']}", headers=headers).status_code == 404


def test_unauthenticated_history_is_401():
    assert client.get("/api/v1/history").status_code == 401


def test_handoff_records_one_entry_per_category():
    headers = _user_headers("9008")
    payload = {
        "request_id": "REQ-TEST-HIST",
        "user_requirements": {
            "occasion": "interview",
            "style": ["smart casual"],
            "identified_items": [{"category": "footwear", "colour": "beige", "role": "requested"}],
        },
        "wardrobe_status": {"available_categories": [], "missing_categories": ["footwear"]},
        "available_items": [],
        "search_requirements": {
            "categories": ["footwear"],
            "style": ["smart casual"],
            "occasion": "interview",
        },
    }
    res = client.post("/api/v1/search/agent1-handoff", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["retrievals"]) == 1

    entries = client.get("/api/v1/history", headers=headers).json()["entries"]
    assert len(entries) == 1
    assert entries[0]["source"] == "agent1_handoff"
    assert entries[0]["request_id"] == "REQ-TEST-HIST:footwear"
