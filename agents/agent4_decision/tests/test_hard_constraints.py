"""
Hard constraints run BEFORE scoring and cannot be outscored:
verifiable products, excluded colours, budget feasibility, availability,
cross-agent consistency, and correlation-ID integrity.
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _recommend(client, auth_headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=auth_headers).json()


def test_unvalidated_product_is_rejected_and_flagged(client, auth_headers):
    # Product in the budget plan that Agent 2 never returned (hallucination guard).
    real = P.product("P-REAL", category="top", price=45.0)
    ghost = P.candidate(P.product("P-GHOST", category="top", price=30.0, name="Phantom shirt"))
    req = P.decision_request(
        options=[
            P.option("OPT-GHOST", products=[ghost]),
            P.option("OPT-REAL", products=[P.candidate(real)]),
        ],
        products_by_category={"top": [real]},  # only real exists in retrieval
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-REAL"
    codes = {(i["code"], i.get("product_id")) for i in body["validation_issues"]}
    assert ("unvalidated_product", "P-GHOST") in codes
    assert all(p["item_id"] != "P-GHOST" for p in body["outfit"])


def test_price_inconsistency_between_sources_is_flagged_not_resolved(client, auth_headers):
    # A2 says USD 40, the budget plan says USD 70 -> beyond tolerance -> reject.
    prod = P.product("P1", price=40.0)
    expensive_candidate = P.candidate(prod).model_copy(update={"price": 70.0})
    good = P.product("P2", price=35.0)
    req = P.decision_request(
        options=[
            P.option("OPT-BAD", products=[expensive_candidate]),
            P.option("OPT-GOOD", products=[P.candidate(good)]),
        ],
        products_by_category={"top": [prod, good]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-GOOD"
    codes = {(i["code"], i.get("product_id")) for i in body["validation_issues"]}
    assert ("price_inconsistency", "P1") in codes
    issue = next(i for i in body["validation_issues"] if i["code"] == "price_inconsistency")
    assert issue["severity"] == "error"


def test_same_product_priced_differently_across_options_flagged(client, auth_headers):
    # A valid copy of the product earlier in the plan must not dedup away the
    # inconsistent copy used by a later option (live-smoke regression).
    prod = P.product("P1", price=40.0)
    req = P.decision_request(
        options=[
            P.option("OPT-GOOD", products=[P.candidate(prod)]),
            P.option("OPT-STALE", products=[P.candidate(prod).model_copy(update={"price": 140.0})]),
        ],
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-GOOD"
    codes = {(i["code"], i.get("product_id")) for i in body["validation_issues"]}
    assert ("price_inconsistency", "P1") in codes


def test_no_false_category_mismatch_when_sources_agree(client, auth_headers):
    prod = P.product("P1", price=40.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req)
    codes = {i["code"] for i in body["validation_issues"]}
    assert "category_mismatch" not in codes


def test_excluded_colour_option_rejected(client, auth_headers):
    green = P.product("P-G", category="top", colour="green", price=20.0)
    white = P.product("P-W", category="top", colour="white", price=50.0)
    req = P.decision_request(
        options=[
            # The excluded-colour option deliberately looks cheaper/better.
            P.option("OPT-GREEN", products=[P.candidate(green)], efficiency=0.99),
            P.option("OPT-WHITE", products=[P.candidate(white)], efficiency=0.3),
        ],
        a1=P.agent1_output(required=["top"], missing=["top"], excluded_colours=["green"]),
        products_by_category={"top": [green, white]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-WHITE"


def test_excluded_colour_in_wardrobe_piece_also_rejected(client, auth_headers):
    # Owned green item repurposed -> hard reject even with zero purchases.
    prod = P.product("P-W", category="top", colour="white", price=50.0)
    req = P.decision_request(
        options=[
            P.option(
                "OPT-GREEN-OWNED",
                products=[],
                wardrobe_items=[P.repurposed("W009", "top", "shirt", "green")],
            ),
            P.option("OPT-BUY", products=[P.candidate(prod)]),
        ],
        a1=P.agent1_output(required=["top"], missing=["top"], excluded_colours=["green"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-BUY"


def test_over_budget_option_rejected(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(
        options=[
            P.option("OPT-OVER", products=[P.candidate(prod)], within_budget=False,
                     budget_ceiling=20.0),
        ],
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["decision"]["status"] == "no_suitable_outfit"
    assert body["selected_combination_id"] is None
    assert body["outfit"] == []
    assert "over budget" in body["explanation"].lower() or "budget" in body["explanation"].lower()


def test_unavailable_product_rejected(client, auth_headers):
    out_of_stock = P.product("P-OOS", price=25.0, availability=False)
    in_stock = P.product("P-IS", price=60.0, availability=True)
    req = P.decision_request(
        options=[
            P.option("OPT-OOS", products=[P.candidate(out_of_stock)], efficiency=0.9),
            P.option("OPT-IS", products=[P.candidate(in_stock)], efficiency=0.4),
        ],
        products_by_category={"top": [out_of_stock, in_stock]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-IS"


def test_request_id_mismatch_blocks_decision(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        products_by_category={"top": [prod]},
    )
    broken = req.model_copy(update={"request_id": "REQ-OTHER-9999"})
    body = _recommend(client, auth_headers, broken)
    assert body["decision"]["status"] == "insufficient_input"
    assert body["decision"]["confidence_score"] <= 0.1
    codes = {i["code"] for i in body["validation_issues"]}
    assert "request_id_mismatch" in codes


def test_clarification_upstream_returns_422(client, auth_headers):
    req = P.decision_request(
        options=[], a1=P.agent1_output(clarification=True)
    )
    r = client.post("/decision/recommend", json=_body(req), headers=auth_headers)
    assert r.status_code == 422
    assert "clarify" in r.json()["detail"].lower() or "mean" in r.json()["detail"].lower()
