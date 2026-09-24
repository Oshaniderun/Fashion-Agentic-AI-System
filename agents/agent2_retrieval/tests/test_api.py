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
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "availability": True,
            "store": "Amazon Fashion",
            "product_url": "https://www.amazon.com/dp/TEST_SHOES_1"
        }
    }


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent2_retrieval"

def test_retrieve_products_unauthorized():
    payload = {
        "request_id": "req_unauth",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/retrieve-products", json=payload)
    assert response.status_code == 401

def test_retrieve_products_with_service_token():
    payload = {
        "request_id": "req_service_tok",
        "required_category": ProductCategory.SHOES.value,
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
        "required_category": ProductCategory.SHOES.value,
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
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/retrieval/search", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req_alias"

def test_api_v1_search_new_alias_exists_and_works():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_new_alias",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req_new_alias"
    assert "status" in data
    assert "results" in data
    assert isinstance(data["results"], list)

def test_api_v1_search_requires_authentication():
    payload = {
        "request_id": "req_search_unauth",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload)
    assert response.status_code == 401

def test_api_v1_search_behaves_identically_to_retrieve_products():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_compare",
        "required_category": ProductCategory.SHOES.value,
        "preferred_colour": "Beige",
        "max_price": 5000.0,
        "top_k": 5
    }
    resp1 = client.post("/retrieve-products", json=payload, headers=headers)
    resp2 = client.post("/api/v1/search", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["status"] == resp2.json()["status"]
    assert len(resp1.json()["results"]) == len(resp2.json()["results"])
    assert resp1.json()["results"][0]["product_id"] == resp2.json()["results"][0]["product_id"]

def test_query_text_sanitization():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_san_query",
        "required_category": ProductCategory.SHOES.value,
        "query_text": "loafers\x00\x08with\x1fstyle",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200
    assert len(response.json()["results"]) > 0

def test_preferred_colour_sanitization():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    # "Beige\x00\x1f" with control chars stripped matches "Beige"
    payload = {
        "request_id": "req_san_colour",
        "required_category": ProductCategory.SHOES.value,
        "preferred_colour": "Beige\x00\x1f",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0
    assert results[0]["product_id"] == "TEST_SHOES_1"

def test_style_sanitization():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    # "smart casual\x07" with control chars stripped matches "smart casual"
    payload = {
        "request_id": "req_san_style",
        "required_category": ProductCategory.SHOES.value,
        "style": "smart casual\x07",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0
    assert results[0]["product_id"] == "TEST_SHOES_1"

def test_occasion_sanitization():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_san_occasion",
        "required_category": ProductCategory.SHOES.value,
        "occasion": "wedding party\x03\x04",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200

def test_max_query_length_boundary():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    huge_query = "shoes " * 500  # > 2000 chars
    payload = {
        "request_id": "req_huge_query",
        "required_category": ProductCategory.SHOES.value,
        "query_text": huge_query,
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 400
    assert "query_text exceeds" in response.text

def test_invalid_top_k_boundaries():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    # top_k = 0
    payload_0 = {
        "request_id": "req_topk_0",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 0
    }
    resp_0 = client.post("/api/v1/search", json=payload_0, headers=headers)
    assert resp_0.status_code in [400, 422]

    # top_k = 50 (> 20)
    payload_50 = {
        "request_id": "req_topk_50",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 50
    }
    resp_50 = client.post("/api/v1/search", json=payload_50, headers=headers)
    assert resp_50.status_code in [400, 422]

def test_invalid_max_price_boundaries():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    # max_price = 0
    payload_0 = {
        "request_id": "req_price_0",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 0.0,
        "top_k": 5
    }
    resp_0 = client.post("/api/v1/search", json=payload_0, headers=headers)
    assert resp_0.status_code in [400, 422]

    # max_price = -100.0
    payload_neg = {
        "request_id": "req_price_neg",
        "required_category": ProductCategory.SHOES.value,
        "max_price": -100.0,
        "top_k": 5
    }
    resp_neg = client.post("/api/v1/search", json=payload_neg, headers=headers)
    assert resp_neg.status_code in [400, 422]

def test_invalid_category():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_invalid_cat",
        "required_category": "automotive_parts",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 422

def test_missing_required_category():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_missing_cat",
        "max_price": 5000.0,
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 422

def test_malformed_request_types():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_bad_type",
        "required_category": ProductCategory.SHOES.value,
        "max_price": "five_thousand_lkr",  # string instead of float
        "top_k": 5
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 422

def test_unknown_fields_safely_ignored():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    payload = {
        "request_id": "req_extra",
        "required_category": ProductCategory.SHOES.value,
        "max_price": 5000.0,
        "top_k": 5,
        "unexpected_extra_metadata": "orchestrator_correlation_999",
        "client_debug_mode": True
    }
    response = client.post("/api/v1/search", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["request_id"] == "req_extra"

def test_product_detail_endpoint_success():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    # Query known existing product in database
    response = client.get("/api/v1/products/B0811M2JG9", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "B0811M2JG9"
    assert "product_name" in data

def test_product_detail_404():
    headers = {"X-Service-Token": settings.SERVICE_TOKEN}
    response = client.get("/api/v1/products/UNKNOWN_PRODUCT_9999", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.text.lower()

def test_product_detail_requires_authentication():
    response = client.get("/api/v1/products/B0811M2JG9")
    assert response.status_code == 401
