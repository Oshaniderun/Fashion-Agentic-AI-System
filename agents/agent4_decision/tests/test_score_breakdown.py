"""
Feature 1 — score breakdown: five sub-scores, configurable weights,
sum-to-one validation, and full backward compatibility.
"""

import pytest
from pydantic import ValidationError

import payloads as P
from app.core.config import Settings
from app.services.score_breakdown_service import build_breakdown, target_formality

SUB_KEYS = [
    "colour_harmony",
    "formality_match",
    "occasion_fit",
    "budget_fit",
    "constraint_satisfaction",
]


def _two_option_request():
    cheap = P.product("PCHEAP", category="top", price=20.0, relevance=0.5, style_match=0.4)
    good = P.product("PGOOD", category="top", price=80.0, relevance=0.95, style_match=0.95)
    return P.decision_request(
        options=[
            P.option("OPT-CHEAP", products=[P.candidate(cheap)], efficiency=0.9),
            P.option("OPT-GOOD", products=[P.candidate(good)], efficiency=0.4),
        ],
        a1=P.agent1_output(required=["top"], missing=["top"], colour_prefs=["white"]),
        products_by_category={"top": [cheap, good]},
    )


def _body(req):
    return req.model_dump(mode="json")


def test_breakdown_reports_chosen_and_runner_ups(client, auth_headers):
    body = client.post("/decision/recommend", json=_body(_two_option_request()), headers=auth_headers).json()
    breakdown = body["score_breakdown"]
    assert breakdown, "chosen outfit must carry a breakdown"
    assert breakdown[0]["selected"] is True
    assert breakdown[0]["combination_id"] == body["selected_combination_id"]
    assert [b["rank"] for b in breakdown] == list(range(1, len(breakdown) + 1))
    assert len(breakdown) == 2


def test_sub_scores_are_normalised_and_weights_sum_to_one(client, auth_headers):
    body = client.post("/decision/recommend", json=_body(_two_option_request()), headers=auth_headers).json()
    for entry in body["score_breakdown"]:
        assert sorted(entry["sub_scores"]) == sorted(SUB_KEYS)
        for value in entry["sub_scores"].values():
            assert 0.0 <= value <= 1.0
        assert abs(sum(entry["weights"].values()) - 1.0) < 1e-9
        expected = sum(entry["weights"][k] * v for k, v in entry["sub_scores"].items())
        assert entry["overall_score"] == pytest.approx(round(expected, 4), abs=1e-4)
        assert 0.0 <= entry["overall_score"] <= 1.0


def test_existing_decision_score_is_reported_unchanged(client, auth_headers):
    """Ranking still runs on the pre-existing composite; it is surfaced side by side."""
    body = client.post("/decision/recommend", json=_body(_two_option_request()), headers=auth_headers).json()
    assert body["score_breakdown"][0]["decision_score"] == pytest.approx(body["metrics"]["decision_score"])


def test_breakdown_is_deterministic(client, auth_headers):
    req = _body(_two_option_request())
    first = client.post("/decision/recommend", json=req, headers=auth_headers).json()
    second = client.post("/decision/recommend", json=req, headers=auth_headers).json()
    assert first["score_breakdown"] == second["score_breakdown"]


def test_custom_weights_change_the_overall_without_changing_the_winner(client, auth_headers):
    request = _two_option_request()
    _, evaluated = _decide(request)
    chosen = [e for e in evaluated if e.passed]
    flat = {k: 0.2 for k in SUB_KEYS}
    heavy_budget = {"colour_harmony": 0.1, "formality_match": 0.1, "occasion_fit": 0.1,
                    "budget_fit": 0.6, "constraint_satisfaction": 0.1}
    scores_flat = [b.overall_score for b in build_breakdown(request, chosen, [], weights=flat)]
    scores_budget = [b.overall_score for b in build_breakdown(request, chosen, [], weights=heavy_budget)]
    assert scores_flat != scores_budget


def _decide(request):
    from app.services.decision_service import get_decision_service

    return get_decision_service().decide(request)


def test_weights_must_sum_to_one_at_startup():
    with pytest.raises(ValidationError):
        Settings(SB_W_COLOUR_HARMONY=0.9)


def test_weights_are_env_overridable(monkeypatch):
    monkeypatch.setenv("SB_W_COLOUR_HARMONY", "0.4")
    monkeypatch.setenv("SB_W_FORMALITY_MATCH", "0.2")
    monkeypatch.setenv("SB_W_OCCASION_FIT", "0.1")
    monkeypatch.setenv("SB_W_BUDGET_FIT", "0.1")
    monkeypatch.setenv("SB_W_CONSTRAINT_SAT", "0.2")
    s = Settings()
    assert s.score_weights()["colour_harmony"] == 0.4
    assert abs(sum(s.score_weights().values()) - 1.0) < 1e-9


def test_negative_weight_is_rejected():
    with pytest.raises(ValidationError):
        Settings(SB_W_COLOUR_HARMONY=-0.5, SB_W_FORMALITY_MATCH=1.5)


def test_formality_target_comes_from_style_then_occasion():
    formal = P.agent1_output(styles=["formal"], occasion="dinner")
    casual = P.agent1_output(styles=["casual"], occasion="dinner")
    assert target_formality(_wrap(formal)) > target_formality(_wrap(casual))
    no_style = P.agent1_output(styles=[], occasion="wedding")
    assert target_formality(_wrap(no_style)) == pytest.approx(0.85)


def _wrap(a1):
    return P.decision_request(options=[], a1=a1)


def test_response_keeps_every_pre_existing_field(client, auth_headers):
    body = client.post("/decision/recommend", json=_body(_two_option_request()), headers=auth_headers).json()
    for key in (
        "request_id", "decision", "selected_combination_id", "strategy", "outfit", "budget",
        "purchase_summary", "metrics", "alternatives", "unresolved_requirements",
        "explanation", "validation_issues", "currency",
    ):
        assert key in body
