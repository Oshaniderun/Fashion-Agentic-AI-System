"""
Feature 3 — explanation faithfulness verification.

Unit-level: the verifier accepts only claims that exist in the supplied data.
Route-level: an unfaithful Gemini polish is discarded for the template, and the
template itself is verified too.
"""

import payloads as P
from app.services import explanation_verifier as V


def _body(req):
    return req.model_dump(mode="json")


def _request():
    prod = P.product("P1", category="top", price=45.0, name="White silk blouse")
    other = P.product("P2", category="top", price=60.0, name="Ivy cotton shirt")
    return P.decision_request(
        options=[
            P.option("OPT-A", products=[P.candidate(prod)]),
            P.option("OPT-B", products=[P.candidate(other)]),
        ],
        a1=P.agent1_output(required=["top"], missing=["top"], colour_prefs=["white"]),
        products_by_category={"top": [prod, other]},
    )


def _post(client, auth_headers, req, params=""):
    return client.post(
        f"/decision/recommend{params}", json=_body(req), headers=auth_headers
    )


def _check(req, text):
    return V.verify(text, req)


# ---------------------------------------------------------------- units


def test_template_text_from_the_engine_is_faithful(client, auth_headers):
    req = _request()
    body = _post(client, auth_headers, req).json()
    assert body["explanation_source"] == "template"
    assert body["explanation_verified"] is True
    assert body["verification_issues"] == []


def test_invented_amount_is_caught():
    req = _request()
    result = _check(req, "The total additional cost is USD 999.00 for this look.")
    assert result.verified is False
    assert any(i.startswith("amount_not_in_data") for i in result.issues)


def test_real_amounts_and_option_differences_are_accepted():
    req = _request()
    result = _check(
        req,
        "USD 45.00 now, USD 60.00 for the other plan, so USD 15.00 apart within "
        "your USD 200.00 budget and USD 155.00 unused.",
    )
    assert result.verified is True, result.issues


def test_invented_item_name_is_caught():
    req = _request()
    result = _check(req, 'Selected “White silk blouse” and “Crimson leather belt”.')
    assert result.verified is False
    assert "name_not_in_data: Crimson leather belt" in result.issues
    assert not any(i.startswith("name_not_in_data: White") for i in result.issues)


def test_invented_colour_is_caught():
    req = _request()
    result = _check(req, "The navy trousers finish this outfit.")
    assert result.verified is False
    assert "colour_not_in_data: navy" in result.issues


def test_stated_preference_colour_is_accepted():
    req = _request()
    result = _check(req, "It matches your white colour preference.")
    assert result.verified is True, result.issues


def test_discount_and_percentage_claims_are_caught():
    req = _request()
    result = _check(req, "You save 30% with a store voucher on this one.")
    assert result.verified is False
    assert any(i.startswith("unverifiable_claim") for i in result.issues)


def test_invented_retailer_is_caught_but_a_real_store_is_not():
    req = _request()
    invented = _check(req, "Available at Amazon within two days.")
    assert "store_not_in_data: amazon" in invented.issues

    real = _check(req, "Sold by Test Retailer.")
    assert real.verified is True, real.issues


def test_invented_identifier_is_caught():
    req = _request()
    result = _check(req, "Option OPT-A pairs SKU-4471-X with your wardrobe.")
    assert result.verified is False
    assert "identifier_not_in_data: SKU-4471-X" in result.issues
    assert not any(i.startswith("identifier_not_in_data: OPT-A") for i in result.issues)


def test_arithmetic_of_total_budget_remaining_is_checked():
    req = _request()
    wrong = _check(
        req,
        "The total additional cost is USD 45.00 against your USD 200.00 budget, "
        "leaving USD 120.00 to spare.",
    )
    assert wrong.verified is False
    assert any(i.startswith("arithmetic_mismatch") for i in wrong.issues)

    right = _check(
        req,
        "The total additional cost is USD 45.00 against your USD 200.00 budget, "
        "leaving USD 155.00 to spare.",
    )
    assert right.verified is True, right.issues


def test_issue_list_is_capped():
    from app.core.config import get_settings

    req = _request()
    text = " ".join(
        f"USD {900 + i:.2f} at Navy by Zara with SKU-{9000 + i}-X “Ghost item {i}”."
        for i in range(30)
    )
    result = _check(req, text)
    assert result.verified is False
    assert len(result.issues) <= get_settings().MAX_VERIFICATION_ISSUES


# ---------------------------------------------------------------- routes


def test_unfaithful_llm_polish_is_discarded_for_the_template(client, auth_headers, monkeypatch):
    req = _request()
    template = _post(client, auth_headers, req).json()
    bad = "Absolutely perfect! Only USD 12.34, 40% off at Amazon, plus a navy silk tie."

    class Stub:
        def generate_explanation(self, **kwargs):
            return bad

    from app.services import llm_explanation_service

    monkeypatch.setattr(llm_explanation_service, "get_llm_explanation_service", lambda: Stub())
    polished = _post(client, auth_headers, req, params="?llm_polish=true").json()

    assert polished["explanation"] == template["explanation"]
    assert polished["explanation_source"] == "template"
    assert polished["explanation_verified"] is True
    assert polished["decision"] == template["decision"]


def test_faithful_llm_polish_is_kept(client, auth_headers, monkeypatch):
    req = _request()
    good = (
        "Your white silk blouse costs USD 45.00, so USD 155.00 of your USD 200.00 "
        "budget is still unused."
    )

    class Stub:
        def generate_explanation(self, **kwargs):
            return good

    from app.services import llm_explanation_service

    monkeypatch.setattr(llm_explanation_service, "get_llm_explanation_service", lambda: Stub())
    body = _post(client, auth_headers, req, params="?llm_polish=true").json()

    assert body["explanation"] == good
    assert body["explanation_source"] == "llm"
    assert body["explanation_verified"] is True
    assert body["verification_issues"] == []


def test_mock_mode_still_reports_the_template(client, auth_headers):
    req = _request()
    plain = _post(client, auth_headers, req).json()
    polished = _post(client, auth_headers, req, params="?llm_polish=true").json()
    assert polished["explanation"] == plain["explanation"]
    assert polished["explanation_source"] == "template"
    assert polished["explanation_verified"] is True


def test_a_broken_template_is_reported_not_hidden(client, auth_headers, monkeypatch):
    from app.services.decision_service import get_decision_service

    svc = get_decision_service()
    original = svc.explanations.build
    monkeypatch.setattr(
        svc.explanations,
        "build",
        lambda **kwargs: "A superb pick at 25% off from Shein, only USD 7.77.",
    )
    try:
        body = _post(client, auth_headers, _request()).json()
    finally:
        monkeypatch.setattr(svc.explanations, "build", original)

    assert body["explanation_verified"] is False
    assert body["explanation_source"] == "template"
    assert any(i.startswith("unverifiable_claim") for i in body["verification_issues"])
    assert any(i.startswith("amount_not_in_data") for i in body["verification_issues"])
