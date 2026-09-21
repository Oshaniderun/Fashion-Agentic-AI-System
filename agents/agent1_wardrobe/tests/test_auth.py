"""
Tests for User Registration, Authentication, and JWT Token Issuance.
"""

def test_register_and_login_flow(client):
    # 1. Register new user
    reg_resp = client.post("/api/auth/register", json={
        "name": "Alex Stylist",
        "email": "alex@fashion.ai",
        "password": "securepassword123"
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert "access_token" in data
    assert data["email"] == "alex@fashion.ai"

    # 2. Login with valid credentials
    login_resp = client.post("/api/auth/login", json={
        "email": "alex@fashion.ai",
        "password": "securepassword123"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    token = login_data["access_token"]

    # 3. Access protected /api/auth/me
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Alex Stylist"


def test_duplicate_registration_fails(client):
    client.post("/api/auth/register", json={
        "name": "Alex",
        "email": "alex@duplicate.ai",
        "password": "password123"
    })
    resp = client.post("/api/auth/register", json={
        "name": "Alex Twin",
        "email": "alex@duplicate.ai",
        "password": "password456"
    })
    assert resp.status_code == 400


def test_invalid_login_credentials(client):
    resp = client.post("/api/auth/login", json={
        "email": "alex@notfound.ai",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


def test_protected_route_requires_jwt(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
