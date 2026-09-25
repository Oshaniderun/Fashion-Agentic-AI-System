"""Auth, IDOR, quota, PII-scrubbing, redirect allow-list and leakage tests."""

import time
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    scrub_pii,
    validate_tenant_access,
    verify_service_token,
)

settings = get_settings()

OPT_PAYLOAD = {
    "request_id": "REQ-SEC",
    "budget": 100.0,
    "missing_categories": ["bottom"],
    "candidate_products_by_category": {},
    "available_wardrobe": [],
}


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_missing_authorization_rejected(client):
    assert client.post("/budget/optimize", json=OPT_PAYLOAD).status_code == 401


def test_invalid_service_token_rejected(client):
    assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer("nope")).status_code == 401


def test_expired_jwt_rejected(client):
    tok = create_access_token(42, expires_delta=timedelta(minutes=-5))
    assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok)).status_code == 401


def test_service_token_accepted(client, auth_headers):
    assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=auth_headers).status_code == 200


def test_x_service_token_header_accepted(client):
    r = client.post(
        "/budget/optimize", json=OPT_PAYLOAD, headers={"X-Service-Token": settings.AGENT_SERVICE_TOKEN}
    )
    assert r.status_code == 200


def test_user_jwt_works_for_own_profile(client):
    tok = create_access_token(42)
    r = client.get("/budget/usage/42", headers=_bearer(tok))
    assert r.status_code == 200
    assert r.json()["tier"] == "free"


def test_idor_blocks_cross_user_usage(client):
    tok = create_access_token(42)
    assert client.get("/budget/usage/99", headers=_bearer(tok)).status_code == 403


def test_idor_blocks_cross_user_optimize(client):
    tok = create_access_token(42)
    payload = dict(OPT_PAYLOAD, user_id="99")
    assert client.post("/budget/optimize", json=payload, headers=_bearer(tok)).status_code == 403


def test_service_may_act_for_any_user(client, auth_headers):
    payload = dict(OPT_PAYLOAD, user_id="99")
    assert client.post("/budget/optimize", json=payload, headers=auth_headers).status_code == 200


def test_free_tier_quota_blocks_fourth_recommendation(client):
    tok = create_access_token(123)
    for _ in range(3):
        assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok)).status_code == 200
    r = client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok))
    assert r.status_code == 429
    assert "Free tier limit" in r.json()["detail"]


def test_premium_bypasses_quota(client, auth_headers):
    tok = create_access_token(555)
    for _ in range(3):
        assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok)).status_code == 200
    assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok)).status_code == 429
    assert client.post(
        "/budget/subscription/upgrade",
        json={"user_id": "555"},
        headers=_bearer(tok),
    ).status_code == 200
    assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=_bearer(tok)).status_code == 200


def test_service_token_usage_not_counted(client, auth_headers):
    for _ in range(5):
        assert client.post("/budget/optimize", json=OPT_PAYLOAD, headers=auth_headers).status_code == 200
    r = client.get("/budget/usage/nosuchuser", headers=auth_headers)
    assert r.json()["recommendations_used"] == 0


def test_pii_scrubbing():
    assert "[REDACTED_FINANCIAL_CARD]" in scrub_pii("card 4111 1111 1111 1111")
    assert "[REDACTED_EMAIL]" in scrub_pii("reach me at a@b.com")
    assert "[REDACTED_PHONE]" in scrub_pii("tel +94771234567")


def test_affiliate_redirect_blocks_foreign_domains(client):
    assert client.get(
        "/budget/affiliate/redirect/X", params={"destination": "https://evil.example.com/phish"}
    ).status_code == 400
    assert client.get(
        "/budget/affiliate/redirect/X", params={"destination": "http://amazon.com/x"}
    ).status_code == 400  # http not allowed
    assert client.get(
        "/budget/affiliate/redirect/X", params={"destination": "https://amazon.com.evil.io/x"}
    ).status_code == 400  # suffix spoof
    r = client.get(
        "/budget/affiliate/redirect/X",
        params={"destination": "https://www.amazon.com/dp/X"},
        follow_redirects=False,
    )
    assert r.status_code == 302


def test_affiliate_redirect_missing_destination_404(client):
    assert client.get("/budget/affiliate/redirect/X").status_code == 404


def test_affiliate_stats_requires_service_principal(client, user_headers):
    assert client.get("/budget/affiliate/stats", headers=user_headers).status_code == 403
    assert client.get(
        "/budget/affiliate/stats",
        headers={"Authorization": f"Bearer {settings.AGENT_SERVICE_TOKEN}"},
    ).status_code == 200


def test_security_headers_present(client):
    r = client.get("/budget/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_constant_time_token_comparison():
    good = settings.AGENT_SERVICE_TOKEN
    near = good[: len(good) - 1] + ("X" if good[-1] != "X" else "Y")
    empty = ""

    def _time(tok):
        start = time.perf_counter_ns()
        for _ in range(100):
            verify_service_token(tok)
        return (time.perf_counter_ns() - start) // 100

    assert verify_service_token(good) is True
    assert verify_service_token(near) is False
    t_good, t_near, t_empty = _time(good), _time(near), _time(empty)
    # Timing must not scale with how much of the token matches
    assert max(t_good, t_near) < 10 * min(t_good, t_near) + 10_000
    assert t_empty < t_good  # empty short-circuits before comparison


def test_validation_error_does_not_leak_secrets(client, auth_headers):
    r = client.post("/budget/optimize", json={"request_id": "X"}, headers=auth_headers)
    assert r.status_code == 422
    body = r.text
    assert settings.JWT_SECRET not in body
    assert settings.AGENT_SERVICE_TOKEN not in body
    assert settings.DATABASE_URL not in body
