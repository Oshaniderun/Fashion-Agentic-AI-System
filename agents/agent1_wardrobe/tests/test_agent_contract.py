"""
Tests for Agent 1 Inter-Agent Contract, JSON Schemas, and Status Endpoints.
"""

from shared.schemas.agent1_schemas import Agent1OutputContract


def _auth_headers(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@fashora.ai", "password": "password123"},
    )
    assert login.status_code == 200
    data = login.json()
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "user_id": data["user_id"],
    }


def test_agent_analyze_requires_auth(client):
    resp = client.post(
        "/api/agent/analyze",
        json={"query_text": "Need something elegant for an engagement."},
    )
    assert resp.status_code == 401


def test_agent_analyze_contract_conformance(client):
    """
    Verifies that POST /api/agent/analyze returns a response that strictly validates
    under Agent1OutputContract Pydantic model.
    """
    auth = _auth_headers(client)
    payload = {
        "user_id": auth["user_id"],
        "query_text": "I need something elegant but not too formal for my cousin's engagement. I don't want bright colours.",
        "occasion": "engagement",
        "budget": 8000.0,
    }
    resp = client.post(
        "/api/agent/analyze",
        json=payload,
        headers={"Authorization": auth["Authorization"]},
    )
    assert resp.status_code == 200
    json_data = resp.json()

    contract = Agent1OutputContract.model_validate(json_data)

    assert contract.request_id.startswith("REQ-")
    assert contract.user_requirements.occasion == "engagement"
    assert "bright" in contract.user_requirements.excluded_colours
    assert len(contract.wardrobe) >= 3

    assert "top" in contract.outfit_requirements.required_categories
    assert "bottom" in contract.outfit_requirements.required_categories

    assert contract.search_requirements.occasion == "engagement"
    assert contract.search_requirements.budget_remaining == 8000.0


def test_agent_analyze_with_service_token(client):
    auth = _auth_headers(client)
    from app.core.config import settings

    resp = client.post(
        "/api/agent/analyze",
        json={
            "user_id": auth["user_id"],
            "query_text": "Smart casual outfit for university.",
        },
        headers={"Authorization": f"Bearer {settings.AGENT_SERVICE_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["user_requirements"]["occasion"] == "university"


def test_agent_schema_endpoint(client):
    resp = client.get("/api/agent/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert "input_contract_schema" in data
    assert "output_contract_schema" in data
    assert data["agent"] == "Agent 1 - Style & Wardrobe Intelligence"


def test_agent_status_and_health(client):
    status_resp = client.get("/api/agent/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "healthy"
    assert "nlp_requirement_extraction" in status_data["capabilities"]
    assert "seed_demo_data" in status_data

    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"
