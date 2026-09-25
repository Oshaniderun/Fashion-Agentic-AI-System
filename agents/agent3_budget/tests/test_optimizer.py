"""
Unit tests: deterministic optimizer, buy-nothing mode, alternatives feedback.
All amounts USD.
"""

from shared.schemas.agent1_schemas import WardrobeSummaryItem
from shared.schemas.agent3_schemas import (
    BudgetOptimizationRequest,
    BudgetStatus,
    CandidateProductItem,
    OptimizationStrategy,
)

from app.services.buy_nothing_service import WardrobeFitCriteria, get_buy_nothing_service
from app.services.optimizer_service import get_optimizer_service
from app.services.explanation_service import get_explanation_service


def cand(pid, cat, price, rel=0.8):
    return CandidateProductItem(
        product_id=pid,
        name=f"{pid} {cat}",
        category=cat,
        colour="black",
        price=price,
        store="Amazon",
        url=f"https://www.amazon.com/dp/{pid}",
        relevance_score=rel,
    )


def wardrobe():
    return [
        WardrobeSummaryItem(wardrobe_id="W001", category="top", type="blouse", colour="white"),
        WardrobeSummaryItem(wardrobe_id="W002", category="footwear", type="loafer", colour="brown"),
    ]


def make_req(**kw):
    base = dict(
        request_id="REQ-U1",
        budget=100.0,
        missing_categories=["bottom"],
        candidate_products_by_category={
            "bottom": [cand("P1", "bottom", 40.0, 0.9), cand("P2", "bottom", 25.0, 0.6)],
        },
        available_wardrobe=wardrobe(),
    )
    base.update(kw)
    return BudgetOptimizationRequest(**base)


def test_within_budget_picks_feasible_options():
    resp = get_optimizer_service().optimize(make_req())
    assert resp.status == BudgetStatus.WITHIN_BUDGET
    assert resp.cheapest_combination_cost == 25.0
    assert resp.recommended_option_id is not None
    for opt in resp.options:
        assert opt.cost_breakdown.total_cost <= resp.budget_ceiling
        assert opt.is_within_budget


def test_money_math_is_exact_usd():
    resp = get_optimizer_service().optimize(make_req(budget=100.0))
    opt = next(o for o in resp.options if o.combination_id == "OPT-BEST-VALUE")
    # Best value maximizes 0.6*relevance + 0.4*(1 - cost/budget) -> P1 (rel 0.9)
    assert opt.cost_breakdown.total_cost == 40.0
    assert opt.cost_breakdown.budget_remaining == 60.0
    assert opt.cost_breakdown.savings_amount == 60.0
    assert opt.cost_breakdown.savings_percentage == 60.0
    assert "USD" in opt.financial_explanation
    assert "LKR" not in opt.financial_explanation


def test_exceeds_budget_triggers_feedback_directives():
    resp = get_optimizer_service().optimize(make_req(budget=10.0, available_wardrobe=[]))
    assert resp.status == BudgetStatus.EXCEEDS_BUDGET
    assert resp.recommended_option_id is None
    assert resp.feedback_loop_recommendations
    rec = resp.feedback_loop_recommendations[0]
    assert rec.category == "bottom"
    assert rec.current_lowest_price == 25.0
    assert rec.target_max_price <= resp.budget_ceiling
    assert rec.action in ("request_cheaper_alternatives", "relax_colour_or_brand")


def test_excluded_product_ids_are_never_selected():
    resp = get_optimizer_service().optimize(make_req(excluded_product_ids=["P1", "P2"]))
    chosen = {p.product_id for o in resp.options for p in o.selected_products}
    assert chosen == set()
    # Nothing left to buy and the wardrobe holds no bottom (or substitute),
    # so no zero-spend option is offered either — honest over-budget report.
    assert resp.status == BudgetStatus.EXCEEDS_BUDGET
    assert resp.recommended_option_id is None
    assert resp.options == []


def test_buy_nothing_only_offers_relevant_wardrobe_items():
    resp = get_optimizer_service().optimize(
        make_req(excluded_product_ids=["P1", "P2"], missing_categories=["footwear", "top"])
    )
    bn = next(o for o in resp.options if o.strategy == OptimizationStrategy.BUY_NOTHING)
    used_ids = {w.wardrobe_id for w in bn.wardrobe_items_used}
    assert used_ids == {"W001", "W002"}  # one per needed category, not all items
    assert all(w.cost == 0.0 for w in bn.wardrobe_items_used)


def test_category_price_caps_filter_candidates():
    resp = get_optimizer_service().optimize(
        make_req(max_price_per_category={"bottom": 30.0})
    )
    for opt in resp.options:
        for p in opt.selected_products:
            assert p.price <= 30.0


def test_no_missing_categories_means_no_purchase_needed():
    resp = get_optimizer_service().optimize(make_req(missing_categories=[]))
    assert resp.status == BudgetStatus.NO_PURCHASE_NEEDED
    assert resp.cheapest_combination_cost == 0.0


def test_buy_nothing_offers_zero_cost_option():
    resp = get_optimizer_service().optimize(
        make_req(budget=10.0, missing_categories=["footwear", "top"])
    )
    assert resp.buy_nothing_available
    bn = next(o for o in resp.options if o.strategy == OptimizationStrategy.BUY_NOTHING)
    assert bn.cost_breakdown.total_cost == 0.0
    assert bn.cost_breakdown.savings_percentage == 100.0
    assert all(item.cost == 0.0 for item in bn.wardrobe_items_used)


def test_buy_nothing_type_substitution():
    opt = get_buy_nothing_service().assemble_buy_nothing_option(
        budget_ceiling=50.0,
        missing_categories=["shoes"],
        available_wardrobe=[
            WardrobeSummaryItem(wardrobe_id="W9", category="footwear", type="heel", colour="black")
        ],
    )
    assert opt is not None
    assert opt.wardrobe_items_used[0].wardrobe_id == "W9"


def test_buy_nothing_empty_wardrobe_returns_none():
    assert get_buy_nothing_service().assemble_buy_nothing_option(50.0, ["top"], []) is None


def test_strict_criteria_hides_category_only_items():
    crit = WardrobeFitCriteria.from_request(["W9"], ["navy"], ["orange"], ["smart_casual"])
    # red blouse fits the category but carries zero compatibility signals -> hidden
    opt = get_buy_nothing_service().assemble_buy_nothing_option(
        budget_ceiling=50.0,
        missing_categories=["top"],
        available_wardrobe=[
            WardrobeSummaryItem(wardrobe_id="W1", category="top", type="blouse", colour="red")
        ],
        criteria=crit,
    )
    assert opt is None


def test_criteria_never_shows_excluded_colour():
    crit = WardrobeFitCriteria.from_request(["W1"], [], ["red"], [])
    picked = get_buy_nothing_service().select_replacements(
        ["top"],
        [WardrobeSummaryItem(wardrobe_id="W1", category="top", type="blouse", colour="red")],
        criteria=crit,
    )
    assert picked == []


def test_criteria_ranks_compatible_over_colour_only_match():
    crit = WardrobeFitCriteria.from_request(["W3"], ["navy"], [], ["smart_casual"])
    picked = get_buy_nothing_service().select_replacements(
        ["top"],
        [
            WardrobeSummaryItem(wardrobe_id="W1", category="top", type="blouse", colour="red"),
            WardrobeSummaryItem(wardrobe_id="W2", category="top", type="shirt", colour="navy"),
            WardrobeSummaryItem(
                wardrobe_id="W3", category="top", type="tee", colour="blue", style="smart_casual"
            ),
        ],
        criteria=crit,
    )
    assert [w.wardrobe_id for _c, w in picked] == ["W3"]  # compatible + style beats colour alone


def test_deterministic_explanations_vary_by_strategy():
    svc = get_explanation_service()
    from shared.schemas.agent3_schemas import CostBreakdown

    cb = CostBreakdown(
        total_cost=20.0, budget_ceiling=50.0, budget_remaining=30.0,
        savings_amount=30.0, savings_percentage=60.0, cost_per_category={"top": 20.0},
    )
    for strat, kw in [
        (OptimizationStrategy.BUY_NOTHING, []),
        (OptimizationStrategy.BEST_VALUE, [cand("P1", "top", 20.0)]),
        (OptimizationStrategy.TOP_MATCH, [cand("P1", "top", 20.0)]),
        (OptimizationStrategy.MINIMAL_PURCHASE, [cand("P1", "top", 20.0)]),
    ]:
        text = svc.generate_explanation(strat, kw, cb, 0.8)
        assert isinstance(text, str) and text
        assert "LKR" not in text


def test_optimizer_is_deterministic_across_runs():
    r1 = get_optimizer_service().optimize(make_req())
    r2 = get_optimizer_service().optimize(make_req())
    assert [o.combination_id for o in r1.options] == [o.combination_id for o in r2.options]
    assert r1.recommended_option_id == r2.recommended_option_id
    for a, b in zip(r1.options, r2.options):
        assert a.cost_breakdown.total_cost == b.cost_breakdown.total_cost
        assert a.overall_value_score == b.overall_value_score
