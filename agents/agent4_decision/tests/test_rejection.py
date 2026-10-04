"""
Feature 2 — structured rejection codes and the re-optimization retry cap.

The retry cap must not change any decision below the cap; it only converts a
call that would have answered "no suitable outfit" into a best-available
answer flagged with retry_limit_reached.
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _recommend(client, auth_headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=auth_headers)


def _round(client, auth_headers, req, n):
    payload = _body(req)
    payload["reoptimization_round"] = n
    return client.post("/decision/recommend", json=payload, headers=auth_headers)


def _codes(rejection):
    return set(rejection["reason_codes"])


def test_over_budget_candidate_gets_structured_rejection(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    ok = P.product("P-OK", category="top", price=45.0)
    req = P.decision_request(
        options=[
            P.option("OPT-OVER", products=[P.candidate(over)], budget_ceiling=200.0,
                     within_budget=False),
            P.option("OPT-OK", products=[P.candidate(ok)]),
        ],
        products_by_category={"top": [over, ok]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["selected_combination_id"] == "OPT-OK"
    (rej,) = body["candidate_rejections"]
    assert rej["combination_id"] == "OPT-OVER"
    assert _codes(rej) == {"OVER_BUDGET"}
    assert rej["product_ids"] == ["P-OVER"]
    assert rej["detail"]


def test_rejected_products_are_exported_for_the_existing_exclusion_flow(client, auth_headers):
    ghost = P.candidate(P.product("P-GHOST", category="top", price=30.0))
    real = P.product("P-REAL", category="top", price=45.0)
    req = P.decision_request(
        options=[
            P.option("OPT-GHOST", products=[ghost]),
            P.option("OPT-REAL", products=[P.candidate(real)]),
        ],
        products_by_category={"top": [real]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["excluded_product_ids"] == ["P-GHOST"]
    assert all(isinstance(i, str) for i in body["excluded_product_ids"])
    assert body["suggested_action"] in {"retry_with_exclusions", "relax_constraints"}


def test_no_suitable_outfit_reports_decision_level_reason_codes(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["decision"]["status"] == "no_suitable_outfit"
    assert body["selected_combination_id"] is None
    assert "OVER_BUDGET" in body["reason_codes"]
    assert "LOW_CONFIDENCE" in body["reason_codes"]
    assert body["retry_limit_reached"] is False
    assert body["retry_limit_reason"] is None


def test_complete_outfit_reports_no_rejection_codes(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top"], missing=["top"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["decision"]["status"] == "complete"
    assert body["reason_codes"] == []
    assert body["candidate_rejections"] == []
    assert body["excluded_product_ids"] == []


def test_partial_outfit_reports_missing_category(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top", "footwear"], missing=["top"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["decision"]["status"] == "partial"
    assert "MISSING_REQUIRED_CATEGORY" in body["reason_codes"]
    assert "INCOMPLETE_OUTFIT" in body["reason_codes"]
    assert body["unresolved_requirements"] == ["footwear"]


def test_below_cap_still_rejects(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    body = _round(client, auth_headers, req, 2).json()
    assert body["retry_limit_reached"] is False
    assert body["selected_combination_id"] is None
    assert body["decision"]["status"] == "no_suitable_outfit"


def test_at_cap_returns_best_available_instead_of_rejecting(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    body = _round(client, auth_headers, req, 3).json()
    assert body["retry_limit_reached"] is True
    assert body["selected_combination_id"] == "OPT-OVER"
    assert body["decision"]["confidence_level"] == "low"
    assert body["decision"]["confidence_score"] < 0.5
    assert body["suggested_action"] == "accept_best_available"
    assert "OPT-OVER" in body["retry_limit_reason"]
    # the caller still learns what is wrong with the forced answer
    assert "OVER_BUDGET" in body["reason_codes"]
    assert body["budget"]["within_budget"] is False


def test_at_cap_prefers_a_buy_nothing_option(client, auth_headers):
    # Only two candidates survive to the cap round: an over-budget purchase and
    # a zero-spend wardrobe look rejected for an excluded colour. The forced
    # answer must be the one that spends nothing.
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[
            P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False),
            P.option(
                "OPT-NOTHING",
                products=[],
                wardrobe_items=[P.repurposed("W002", "top", "blouse", "black")],
            ),
        ],
        a1=P.agent1_output(
            required=["top"],
            missing=["top"],
            excluded_colours=["black"],
            wardrobe=[P.wardrobe_item("W002", "top", "blouse", "black")],
        ),
        products_by_category={"top": [over]},
    )
    baseline = _round(client, auth_headers, req, 0).json()
    assert baseline["selected_combination_id"] is None
    assert _codes(baseline["candidate_rejections"][1]) == {"STYLE_CLASH"}

    body = _round(client, auth_headers, req, 3).json()
    assert body["selected_combination_id"] == "OPT-NOTHING"
    assert body["purchase_summary"]["purchase_count"] == 0
    assert body["decision"]["confidence_level"] == "low"


def test_at_cap_with_no_candidates_at_all_still_reports(client, auth_headers):
    req = P.decision_request(options=[])
    body = _round(client, auth_headers, req, 5).json()
    assert body["retry_limit_reached"] is True
    assert body["selected_combination_id"] is None
    assert body["retry_limit_reason"]


def test_round_is_echoed_and_defaults_to_zero(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        products_by_category={"top": [prod]},
    )
    assert _recommend(client, auth_headers, req).json()["reoptimization_round"] == 0
    assert _round(client, auth_headers, req, 2).json()["reoptimization_round"] == 2


def test_excluded_product_ids_are_capped(client, auth_headers):
    from app.core.config import get_settings

    products = [P.product(f"P{i}", category="top", price=20.0 + i) for i in range(4)]
    options = [
        P.option(f"OPT-{p.product_id}", products=[P.candidate(p)], within_budget=False)
        for p in products
    ]
    req = P.decision_request(
        options=options, products_by_category={"top": products}
    )
    body = _recommend(client, auth_headers, req).json()
    assert len(body["excluded_product_ids"]) == len(products)
    assert len(body["excluded_product_ids"]) <= get_settings().MAX_EXCLUDED_PRODUCT_IDS


def test_missing_round_field_keeps_today_behaviour(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        products_by_category={"top": [prod]},
    )
    payload = _body(req)
    payload.pop("reoptimization_round", None)
    assert "reoptimization_round" not in payload  # old callers send no such field
    omitted = client.post("/decision/recommend", json=payload, headers=auth_headers).json()
    explicit = _round(client, auth_headers, req, 0).json()
    assert omitted == explicit
    assert omitted["retry_limit_reached"] is False
    assert omitted["decision"]["status"] == "complete"


def test_forced_low_score_is_configured_below_the_threshold():
    from app.core.config import Settings

    s = Settings()
    assert 0.0 <= s.FORCED_LOW_CONFIDENCE_SCORE < s.LOW_CONFIDENCE_THRESHOLD
