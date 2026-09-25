"""
Pipeline adapter tests: plan-purchases from REAL Agent 1 / Agent 2 contracts,
budget-source policy, no-invented-price handling, and the Agent 3 <-> Agent 2
cheaper-alternatives feedback loop (stub retrieval, forwarded auth).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from shared.schemas.agent1_schemas import (
    Agent1OutputContract,
    Agent2SearchRequirement,
    ConfidenceMetrics,
    OutfitRequirements,
    UserRequirements,
    WardrobeSummaryItem,
)
from shared.schemas.agent2_schemas import (
    ProductResult,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalStatus,
    ScoreBreakdown,
)
from shared.schemas.agent3_schemas import BudgetSource, BudgetStatus, PlanPurchasesRequest


def _prod(pid, price, rel=0.8, availability=True):
    return ProductResult(
        product_id=pid,
        name=f"{pid} garment",
        category="dress",
        colour="black",
        price=price,
        store="Amazon",
        url=f"https://www.amazon.com/dp/{pid}" if price else None,
        availability=availability,
        relevance_score=rel,
        score_breakdown=ScoreBreakdown(
            semantic_similarity=rel, colour_match=0.5, style_match=0.5,
            budget_suitability=0.9, availability=1.0,
        ),
    )


def _a1(budget=None, max_price=None, missing=("dress",), clarification=False):
    return Agent1OutputContract(
        request_id="REQ-P1",
        user_requirements=UserRequirements(occasion="interview", style=["formal"], budget=budget),
        wardrobe=[WardrobeSummaryItem(wardrobe_id="W1", category="top", type="blouse", colour="white")],
        outfit_requirements=OutfitRequirements(
            required_categories=list(missing) + ["top"],
            available_categories=["top"],
            missing_categories=list(missing),
            clarification_needed=clarification,
            clarification_message="What is 'xyzabc'?" if clarification else None,
        ),
        confidence=ConfidenceMetrics(overall=0.9),
        search_requirements=Agent2SearchRequirement(categories=list(missing), maximum_price=max_price),
    )


def _retrieval(results):
    return RetrievalResponse(
        request_id="REQ-P1", status=RetrievalStatus.OK, results=results,
    )


def _body(a1, results, **kw):
    return PlanPurchasesRequest(
        agent1_output=a1,
        retrieval_by_category={"dress": _retrieval(results)},
        **kw,
    ).model_dump(mode="json")


def test_user_stated_budget_wins(client, auth_headers):
    body = _body(_a1(budget=60.0, max_price=99.0), [_prod("P1", 45.0, 0.9)])
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()
    assert d["budget_source"] == BudgetSource.USER_STATED.value
    assert d["budget_ceiling"] == 60.0
    assert d["status"] == BudgetStatus.WITHIN_BUDGET.value


def test_search_ceiling_used_when_no_stated_budget(client, auth_headers):
    body = _body(_a1(max_price=50.0), [_prod("P1", 45.0)])
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()
    assert d["budget_source"] == BudgetSource.SEARCH_CEILING.value
    assert d["budget_ceiling"] == 50.0


def test_no_budget_anywhere_refuses_instead_of_inventing(client, auth_headers):
    body = _body(_a1(), [_prod("P1", 45.0)])
    r = client.post("/budget/plan-purchases", json=body, headers=auth_headers)
    assert r.status_code == 422
    assert "budget" in r.json()["detail"].lower()


def test_clarification_needed_is_not_planned_around(client, auth_headers):
    body = _body(_a1(budget=50.0, clarification=True), [])
    r = client.post("/budget/plan-purchases", json=body, headers=auth_headers)
    assert r.status_code == 422
    assert "xyzabc" in r.json()["detail"]


def test_unpriced_products_excluded_from_money_math(client, auth_headers):
    body = _body(
        _a1(budget=60.0),
        [_prod("P1", 45.0), _prod("PNP", None), _prod("PUN", 20.0, availability=False)],
    )
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()
    all_pids = {p["product_id"] for o in d["options"] for p in o["selected_products"]}
    assert "PNP" not in all_pids and "PUN" not in all_pids
    assert "no price" in d["notes"]


class _FakeA2Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeA2Client:
    """Stand-in for httpx.AsyncClient that records calls to Agent 2."""

    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).calls.append({"url": url, "payload": json, "headers": headers or {}})
        cheaper = _retrieval([_prod("CHEAP1", 12.0, 0.75)]).model_dump(mode="json")
        cheaper["request_id"] = json["request_id"]
        return _FakeA2Response(cheaper)


@pytest.fixture
def fake_agent2(monkeypatch):
    _FakeA2Client.calls = []
    import app.api.routes as routes

    monkeypatch.setattr(routes, "_new_async_client", _FakeA2Client)
    return _FakeA2Client


def test_feedback_loop_requests_cheaper_from_agent2(client, auth_headers, fake_agent2):
    # Budget 20: cheapest dress is 40 -> over budget; Agent 2 (stub) then finds 12.
    a1 = _a1(budget=20.0)
    retrieval_req = RetrievalRequest(request_id="REQ-P1", required_category="dress", max_price=20.0)
    body = _body(
        a1,
        [_prod("P1", 40.0, 0.9), _prod("P2", 45.0, 0.8)],
        retrieval_requests_by_category={"dress": retrieval_req},
        enable_feedback_loop=True,
    )
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()

    assert fake_agent2.calls, "Agent 3 must call Agent 2 for cheaper alternatives"
    call = fake_agent2.calls[0]
    assert call["url"].endswith("/api/v1/search")
    assert call["headers"].get("Authorization") == auth_headers["Authorization"]
    payload = call["payload"]
    assert payload["is_retry"] is True
    assert payload["max_price"] <= 20.0
    assert set(payload["excluded_product_ids"]) >= {"P1", "P2"}

    assert d["status"] == BudgetStatus.WITHIN_BUDGET.value
    chosen = {p["product_id"] for o in d["options"] for p in o["selected_products"]}
    assert "CHEAP1" in chosen
    assert d["retry_log"]
    log = d["retry_log"][0]
    assert log["iteration"] == 1 and log["category"] == "dress"
    assert log["previous_lowest_price"] == 40.0 and log["new_products_found"] == 1


def test_feedback_loop_disabled_by_flag(client, auth_headers, fake_agent2):
    retrieval_req = RetrievalRequest(request_id="REQ-P1", required_category="dress", max_price=20.0)
    body = _body(
        _a1(budget=20.0),
        [_prod("P1", 40.0)],
        retrieval_requests_by_category={"dress": retrieval_req},
        enable_feedback_loop=False,
    )
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()
    assert fake_agent2.calls == []
    assert d["retry_log"] == []
    assert d["status"] in (BudgetStatus.EXCEEDS_BUDGET.value, BudgetStatus.PARTIALLY_FEASIBLE.value)


def test_feedback_loop_without_retrieval_requests_stays_local(client, auth_headers, fake_agent2):
    body = _body(_a1(budget=20.0), [_prod("P1", 40.0)])
    d = client.post("/budget/plan-purchases", json=body, headers=auth_headers).json()
    assert fake_agent2.calls == []
    assert d["retry_log"] == []
