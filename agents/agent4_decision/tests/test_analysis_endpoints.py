"""
Diagnostic endpoints: /decision/analyze and /decision/alternatives.
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _scenario():
    good = P.product("P-GOOD", price=45.0, relevance=0.9)
    ghost = P.candidate(P.product("P-GHOST", price=10.0, name="Phantom"))
    req = P.decision_request(
        options=[
            P.option("OPT-GHOST", products=[ghost]),
            P.option("OPT-GOOD", products=[P.candidate(good)]),
        ],
        products_by_category={"top": [good]},
    )
    return req


def test_analyze_shows_every_candidate_and_rejection(client, auth_headers):
    r = client.post("/decision/analyze", json=_body(_scenario()), headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    by_id = {c["combination_id"]: c for c in body["evaluated_candidates"]}
    assert set(by_id) == {"OPT-GHOST", "OPT-GOOD"}
    assert by_id["OPT-GOOD"]["selected"] is True
    assert by_id["OPT-GHOST"]["passed_hard_constraints"] is False
    assert "verified" in by_id["OPT-GHOST"]["rejection_reason"]
    for c in by_id.values():
        assert 0.0 <= c["metrics"]["decision_score"] <= 1.0


def test_alternatives_lists_runners_up_with_reasons(client, auth_headers):
    good2 = P.product("P-G2", price=90.0, relevance=0.6)
    req = P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(P.product("P1", price=45.0))]),
            P.option("OPT-B", products=[P.candidate(good2)]),
        ],
        products_by_category={"top": [P.product("P1", price=45.0), good2]},
    )
    r = client.post("/decision/alternatives", json=_body(req), headers=auth_headers)
    assert r.status_code == 200
    alts = r.json()["alternatives"]
    assert [a["combination_id"] for a in alts] == ["OPT-B"]
    assert alts[0]["within_budget"] is True
    assert alts[0]["reason"]


def test_alternatives_empty_when_no_runner_up(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        products_by_category={"top": [prod]},
    )
    body = client.post("/decision/alternatives", json=_body(req), headers=auth_headers).json()
    assert body["alternatives"] == []
