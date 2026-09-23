"""
Integration tests for Agent 2 FastAPI endpoints:
/health, /retrieve-products, /api/v1/retrieval/search, /api/v1/products/{product_id}
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

from app.main import app
from app.core.security import create_access_token
from app.core.config import get_settings
from app.services.retrieval_service import get_retrieval_service
from shared.constants import ProductCategory

client = TestClient(app)
settings = get_settings()

@pytest.fixture(autouse=True)
def setup_test_catalog():
    service = get_retrieval_service()
    service.products = {
        "TEST_SHOES_1": {
            "product_id": "TEST_SHOES_1",
            "product_name": "Test Loafers",
            "category": "shoes",
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "availability": True,
            "store": "Amazon Fashion",
            "product_url": "https://www.amazon.com/dp/TEST_SHOES_1"
        }
    }
    service.bm25_service.build_from_products(list(service.products.values()))

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent2_retrieval"

def test_retrieve_products_unauthorized():
    payload = {
        "request_id": "req_unauth",
        "required_category": "shoes",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/retrieve-products", json=payload)
    assert response.status_code == 401

def test_retrieve_products_with_service_token():
    payload = {
        "request_id": "req_service_tok",
        "required_category": "shoes",
        "preferred_colour": "Beige",
        "max_price": 5000.0,
        "top_k": 5
    }
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    response = client.post("/retrieve-products", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req_service_tok"
    assert data["status"] in ["ok", "relaxed", "low_confidence"]
    assert len(data["results"]) > 0
    assert data["results"][0]["product_id"] == "TEST_SHOES_1"

def test_retrieve_products_with_jwt():
    token = create_access_token({"sub": "user_123", "role": "shopper"})
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "request_id": "req_jwt",
        "required_category": "shoes",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/retrieve-products", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req_jwt"

def test_api_v1_search_alias():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_alias",
        "required_category": "shoes",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/retrieval/search", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req_alias"
