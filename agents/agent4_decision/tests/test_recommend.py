"""
Core decision behaviour: selection, ranking, budget reuse, determinism,
completeness and confidence.
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _recommend(client, auth_headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=auth_headers)


def test_happy_path_selects_complete_in_budget_option(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[
            P.option(
                "OPT-BEST-VALUE",
                products=[P.candidate(prod)],
                wardrobe_items=[P.repurposed("W002", "footwear", "loafer", "brown")],
            )
        ],
        a1=P.agent1_output(required=["top", "footwear"], missing=["top"]),
        products_by_category={"top": [prod]},
    )
    r = _recommend(client, auth_headers, req)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"]["status"] == "complete"
    assert body["selected_combination_id"] == "OPT-BEST-VALUE"
    sources = {p["source"] for p in body["outfit"]}
    assert sources == {"purchase", "wardrobe"}
    assert body["purchase_summary"] == {"purchase_count": 1, "existing_items_used": 1}


def test_budget_financials_are_reused_not_recomputed(client, auth_headers):
    prod = P.product("P1", price=45.0)
    opt = P.option("OPT-A", products=[P.candidate(prod)], budget_ceiling=200.0)
    req = P.decision_request(
        options=[opt], products_by_category={"top": [prod]}
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["budget"] == {
        "maximum_usd": 200.0,
        "additional_cost_usd": 45.0,
        "remaining_usd": 155.0,
        "within_budget": True,
    }


def test_complete_option_beats_higher_scoring_incomplete_one(client, auth_headers):
    complete_prod = P.product("PC", category="top", price=80.0, relevance=0.5)
    partial_prod = P.product("PP", category="top", price=10.0, relevance=0.99)
    req = P.decision_request(
        options=[
            # partial: covers only 'top' of ['top','footwear'] but scores high
            P.option("OPT-PARTIAL", products=[P.candidate(partial_prod)], efficiency=0.95),
            # complete: covers both required categories
            P.option(
                "OPT-COMPLETE",
                products=[P.candidate(complete_prod)],
                wardrobe_items=[P.repurposed("W002", "footwear", "loafer", "brown")],
                efficiency=0.4,
            ),
        ],
        a1=P.agent1_output(required=["top", "footwear"], missing=["top"]),
        products_by_category={"top": [partial_prod, complete_prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["selected_combination_id"] == "OPT-COMPLETE"
    assert body["decision"]["status"] == "complete"


def test_partial_result_when_nothing_complete(client, auth_headers):
    prod = P.product("P1", category="top", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top", "footwear"], missing=["top"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["decision"]["status"] == "partial"
    assert body["unresolved_requirements"] == ["footwear"]
    assert body["decision"]["confidence_score"] <= 0.65


def test_fewer_purchases_preferred_on_score_tie():
    # Direct ranking-key check: with equal decision_score the tie-break is
    # purchase_count (minimal-purchase goal), then total cost, then id.
    from app.services.decision_service import DecisionService, EvaluatedOption
    from shared.schemas.agent4_schemas import CandidateMetrics

    def metrics(score: float, purchases: int) -> CandidateMetrics:
        return CandidateMetrics(
            occasion_fit=0.8, style_fit=0.8, colour_fit=0.8, wardrobe_reuse=0.5,
            retrieval_relevance=0.8, budget_efficiency=0.7, purchase_count=purchases,
            within_budget=True, is_complete=True, decision_score=score,
        )

    svc = DecisionService.__new__(DecisionService)  # no init needed for _rank_key
    key = svc._rank_key(P.decision_request(options=[]))

    cheap_two = P.option("OPT-B2", products=[])
    zero_buy = P.option("OPT-A0", products=[])
    evals = [
        EvaluatedOption(option=cheap_two, pieces=[], metrics=metrics(0.8, 2),
                        unresolved=[], passed=True, is_complete=True),
        EvaluatedOption(option=zero_buy, pieces=[], metrics=metrics(0.8, 0),
                        unresolved=[], passed=True, is_complete=True),
    ]
    ranked = sorted(evals, key=key)
    assert ranked[0].option.combination_id == "OPT-A0"
    assert ranked[0].metrics.purchase_count == 0


def test_decision_is_deterministic(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(options=[P.option("OPT-A", products=[P.candidate(prod)])],
                             products_by_category={"top": [prod]})
    first = _recommend(client, auth_headers, req).json()
    second = _recommend(client, auth_headers, req).json()
    assert first == second


def test_confidence_high_for_complete_verified_in_budget(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top"], missing=["top"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    assert body["decision"]["confidence_level"] == "high"
    assert body["decision"]["confidence_score"] >= 0.75


def test_explanation_cites_real_numbers_and_no_invented_items(client, auth_headers):
    prod = P.product("P1", price=45.0, name="White silk blouse")
    req = P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top"], missing=["top"], colour_prefs=["white"]),
        products_by_category={"top": [prod]},
    )
    body = _recommend(client, auth_headers, req).json()
    text = body["explanation"]
    assert "45.00" in text and "200.00" in text
    assert "White silk blouse" in text
    assert "agent" not in text.lower()  # user-facing voice is FASHORA, not internals


def test_runner_up_cost_direction_is_named_correctly(client, auth_headers):
    # Chosen outfit and runner-up differ only in price here, so the adjective
    # in the trade-off sentence is the thing under test. Relevance decides
    # which one wins, so both directions are reachable on the same two prices.
    def request(winner_price: float, loser_price: float):
        win = P.product("P-WIN", price=winner_price, relevance=0.99)
        lose = P.product("P-LOSE", price=loser_price, relevance=0.40)
        return P.decision_request(
            options=[
                P.option("OPT-ONE", products=[P.candidate(win)], efficiency=0.9),
                P.option("OPT-TWO", products=[P.candidate(lose)], efficiency=0.3),
            ],
            products_by_category={"top": [win, lose]},
        )

    dearer_runner = _recommend(client, auth_headers, request(45.0, 120.0)).json()
    assert dearer_runner["selected_combination_id"] == "OPT-ONE"
    assert "USD 75.00 more expensive" in dearer_runner["explanation"]
    assert "USD 75.00 cheaper" not in dearer_runner["explanation"]

    cheaper_runner = _recommend(client, auth_headers, request(120.0, 45.0)).json()
    assert cheaper_runner["selected_combination_id"] == "OPT-ONE"
    assert "USD 75.00 cheaper" in cheaper_runner["explanation"]
    assert "USD 75.00 more expensive" not in cheaper_runner["explanation"]


def test_llm_polish_falls_back_to_deterministic_in_mock_mode(client, auth_headers):
    prod = P.product("P1", price=45.0)
    req = P.decision_request(options=[P.option("OPT-A", products=[P.candidate(prod)])],
                             products_by_category={"top": [prod]})
    plain = _recommend(client, auth_headers, req)
    polished = client.post(
        "/decision/recommend?llm_polish=true", json=_body(req), headers=auth_headers
    )
    assert polished.status_code == 200
    assert polished.json()["explanation"] == plain.json()["explanation"]
