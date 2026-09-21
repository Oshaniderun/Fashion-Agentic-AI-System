"""
Tests for persisted fashion analysis history (Phase 2).
"""


def _login(client, email="persist@fashora.ai", password="securepass1", name="Persist User"):
    client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_analysis_persists_and_survives_lookup(client):
    headers = _login(client)

    create = client.post(
        "/api/analyze/request",
        headers=headers,
        json={
            "query_text": "I need something elegant for an engagement. No bright colours.",
        },
    )
    assert create.status_code == 200
    body = create.json()
    request_id = body["request_id"]
    assert request_id.startswith("REQ-")
    assert body["user_requirements"]["occasion"] == "engagement"

    # Fetch by id (DB-backed, not RAM)
    fetched = client.get(f"/api/analyze/{request_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["request_id"] == request_id
    assert fetched.json()["input_text"] == body["input_text"]

    # Latest for dashboard
    latest = client.get("/api/analyze/recent/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json()["request_id"] == request_id


def test_analysis_is_user_isolated(client):
    headers_a = _login(client, email="user_a@fashora.ai", name="User A")
    headers_b = _login(client, email="user_b@fashora.ai", name="User B")

    created = client.post(
        "/api/analyze/request",
        headers=headers_a,
        json={"query_text": "Formal outfit for an interview."},
    )
    assert created.status_code == 200
    request_id = created.json()["request_id"]

    # Owner can read
    assert client.get(f"/api/analyze/{request_id}", headers=headers_a).status_code == 200

    # Other user cannot
    forbidden = client.get(f"/api/analyze/{request_id}", headers=headers_b)
    assert forbidden.status_code == 404

    # Other user's latest is empty / not A's
    latest_b = client.get("/api/analyze/recent/latest", headers=headers_b)
    assert latest_b.status_code == 200
    assert latest_b.json() is None


def test_analysis_endpoints_require_auth(client):
    assert client.get("/api/analyze/recent/latest").status_code == 401
    assert client.get("/api/analyze/REQ-FAKE").status_code == 401
