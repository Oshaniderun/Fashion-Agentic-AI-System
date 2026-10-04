"""
Feature 4 — counterfactual analysis.

Every entry must come from re-running the real engine on a hypothetical input,
never from a language model, and the actual decision must be unaffected.
"""

import payloads as P
from app.schemas.agent4_extensions import SubScores


def _body(req):
    return req.model_dump(mode="json")


def _post(client, auth_headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=auth_headers).json()


def _kind(body, kind):
    return [c for c in body["counterfactuals"] if c["kind"] == kind]


def test_budget_increase_counterfactual_names_the_smallest_flipping_ceiling(client, auth_headers):
    cheap = P.product("P-CHEAP", category="top", price=45.0, relevance=0.6)
    premium = P.product("P-PREMIUM", category="top", price=260.0, relevance=0.98,
                        style_match=0.98, colour_match=0.98)
    req = P.decision_request(
        options=[
            P.option("OPT-CHEAP", products=[P.candidate(cheap)], efficiency=0.3),
            P.option(
                "OPT-PREMIUM",
                products=[P.candidate(premium)],
                efficiency=0.95,
                within_budget=False,
            ),
        ],
        products_by_category={"top": [cheap, premium]},
    )
    body = _post(client, auth_headers, req)

    assert body["selected_combination_id"] == "OPT-CHEAP"
    (cf,) = _kind(body, "budget_increase")
    assert cf["field"] == "budget_response.budget_ceiling"
    assert cf["old_value"] == 200.0
    assert cf["new_value"] == 260.0
    assert cf["resulting_winner"] == "OPT-PREMIUM"
    assert "USD 260.00" in cf["sentence"]
    # the real answer is untouched by the probe
    assert body["budget"] == {
        "maximum_usd": 200.0,
        "additional_cost_usd": 45.0,
        "remaining_usd": 155.0,
        "within_budget": True,
    }


def test_says_so_when_no_budget_change_would_alter_the_result(client, auth_headers):
    first = P.product("P1", category="top", price=45.0, relevance=0.9)
    second = P.product("P2", category="top", price=60.0, relevance=0.5,
                       style_match=0.5, colour_match=0.5)
    req = P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(first)]),
            P.option("OPT-B", products=[P.candidate(second)]),
        ],
        products_by_category={"top": [first, second]},
    )
    body = _post(client, auth_headers, req)
    (cf,) = _kind(body, "no_budget_change")
    assert cf["new_value"] is None
    assert cf["resulting_winner"] == "OPT-A"
    assert "No budget increase" in cf["sentence"]


def test_single_item_swap_counterfactual(client, auth_headers):
    good = P.product("P1", category="top", price=45.0, relevance=0.9)
    runner_up = P.product("P2", category="top", price=50.0, relevance=0.85,
                          style_match=0.85, colour_match=0.85)
    bad = P.product("P3", category="top", price=40.0, colour="neon_orange",
                    relevance=0.05, style_match=0.05, colour_match=0.05)
    req = P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(good)]),
            P.option("OPT-B", products=[P.candidate(runner_up)]),
        ],
        products_by_category={"top": [good, runner_up, bad]},
    )
    body = _post(client, auth_headers, req)

    assert body["selected_combination_id"] == "OPT-A"
    (cf,) = _kind(body, "item_swap")
    assert cf["field"] == "options[OPT-A].products[P1]"
    assert cf["old_value"] == "P1"
    assert cf["new_value"] == "P3"
    assert cf["resulting_winner"] == "OPT-B"
    assert cf["sub_score"] in SubScores.model_fields
    assert "P3" in cf["sentence"] and "OPT-B" in cf["sentence"]


def test_counterfactual_count_is_capped_and_deterministic(client, auth_headers):
    from app.core.config import get_settings

    good = P.product("P1", category="top", price=45.0)
    other = P.product("P2", category="top", price=50.0)
    bad = P.product("P3", category="top", price=40.0, relevance=0.05,
                    style_match=0.05, colour_match=0.05)
    req = P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(good)]),
            P.option("OPT-B", products=[P.candidate(other)]),
        ],
        products_by_category={"top": [good, other, bad]},
    )
    first = _post(client, auth_headers, req)
    second = _post(client, auth_headers, req)
    assert first["counterfactuals"] == second["counterfactuals"]
    assert len(first["counterfactuals"]) <= get_settings().MAX_COUNTERFACTUALS
    assert first["counterfactuals"], "expected at least the swap flip"
    for cf in first["counterfactuals"]:
        assert cf["field"] and cf["sentence"]


def test_no_counterfactuals_without_a_decision(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    assert _post(client, auth_headers, req)["counterfactuals"] == []


def test_forced_answer_at_the_retry_cap_reports_no_counterfactuals(client, auth_headers):
    over = P.product("P-OVER", category="top", price=300.0)
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    payload = _body(req)
    payload["reoptimization_round"] = 3
    body = client.post(
        "/decision/recommend", json=payload, headers=auth_headers
    ).json()
    assert body["retry_limit_reached"] is True
    assert body["counterfactuals"] == []


def test_hypothetical_amounts_never_enter_the_explanation(client, auth_headers):
    good = P.product("P1", category="top", price=45.0, relevance=0.6)
    premium = P.product("P2", category="top", price=260.0, relevance=0.98,
                        style_match=0.98, colour_match=0.98)
    req = P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(good)], efficiency=0.3),
            P.option(
                "OPT-B", products=[P.candidate(premium)], efficiency=0.95, within_budget=False
            ),
        ],
        products_by_category={"top": [good, premium]},
    )
    body = _post(client, auth_headers, req)
    assert _kind(body, "budget_increase")
    assert "260.00" not in body["explanation"]
    assert body["explanation_verified"] is True
