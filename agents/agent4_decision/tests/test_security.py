"""
Auth, IDOR and no-anonymous-access guarantees (same contract as Agents 1-3).
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _simple_request(user_id=None):
    prod = P.product("P1", price=45.0)
    return P.decision_request(options=[P.option("OPT-A", products=[P.candidate(prod)])],
                              products_by_category={"top": [prod]}, user_id=user_id)


def test_no_credentials_is_401(client):
    r = client.post("/decision/recommend", json=_body(_simple_request()))
    assert r.status_code == 401


def test_invalid_token_is_401(client):
    r = client.post(
        "/decision/recommend",
        json=_body(_simple_request()),
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


def test_user_jwt_own_id_accepted(client, user_headers):
    r = client.post(
        "/decision/recommend", json=_body(_simple_request(user_id="42")), headers=user_headers
    )
    assert r.status_code == 200


def test_user_jwt_other_id_idor_blocked(client, user_headers):
    r = client.post(
        "/decision/recommend", json=_body(_simple_request(user_id="7")), headers=user_headers
    )
    assert r.status_code == 403


def test_service_token_may_decide_for_any_user(client, auth_headers):
    r = client.post(
        "/decision/recommend", json=_body(_simple_request(user_id="7")), headers=auth_headers
    )
    assert r.status_code == 200


def test_service_token_via_header(client):
    from app.core.config import get_settings

    r = client.post(
        "/decision/recommend",
        json=_body(_simple_request()),
        headers={"X-Service-Token": get_settings().AGENT_SERVICE_TOKEN},
    )
    assert r.status_code == 200


def test_health_open_no_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/decision/health").status_code == 200
