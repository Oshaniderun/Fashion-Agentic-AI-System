"""
Agent 1 robustness: garbled-word handling in the requested-item position.
Typo correction (dres -> dress), synonym mapping (frock -> dress), and
clarification for terms that cannot be understood — never a silent fallback
to the default full-outfit template.
"""

import pytest

from app.services.llm.structured_extractor import structured_extractor
from app.services.nlp.requirement_extractor import fashion_requirement_service
from app.services.nlp.normalization import correct_garbled_words
from app.services.outfit_requirements import outfit_requirement_engine


@pytest.fixture()
def deterministic(monkeypatch):
    monkeypatch.setattr(structured_extractor, "provider", "mock")
    monkeypatch.setattr(structured_extractor, "api_key", None)


def test_typo_dres_normalized_to_dress(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request("i need a dres")
    assert reqs.requested_categories == ["dress"]
    assert reqs.unrecognized_terms == []
    assert not outfit_requirement_engine.clarification_needed(reqs)
    required, _ = outfit_requirement_engine.determine_requirements(reqs)
    assert required == ["dress"]


def test_synonym_frock_maps_to_dress(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request("I need a frock")
    assert "dress" in reqs.requested_categories
    assert "frock" in reqs.requested_types
    assert not outfit_requirement_engine.clarification_needed(reqs)


def test_unknown_term_asks_clarification_and_invents_nothing(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request("i need a xyzabc")
    assert reqs.requested_categories == []
    assert reqs.unrecognized_terms == ["xyzabc"]
    assert outfit_requirement_engine.clarification_needed(reqs)
    required, optional = outfit_requirement_engine.determine_requirements(reqs)
    # The dangerous old behavior: silent [top, bottom, footwear] default.
    assert required == []
    assert optional == []
    msg = outfit_requirement_engine.clarification_message(reqs)
    assert "xyzabc" in msg


def test_multiple_typos_corrected_or_clarified(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request("I ned a whte dres")
    assert reqs.requested_categories == ["dress"]
    assert not outfit_requirement_engine.clarification_needed(reqs)


def test_transposition_typo_in_pattern_word(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request("i want a chekced shirt")
    assert "top" in reqs.requested_categories
    assert "checked" in reqs.pattern_preferences


def test_correction_unit_cases():
    text, corr, unrec = correct_garbled_words("i need a dres")
    assert text == "i need a dress" and corr == {"dres": "dress"} and unrec == []
    _, _, unrec2 = correct_garbled_words("i need a xyzabc")
    assert unrec2 == ["xyzabc"]
    # Known-vocabulary sentences are untouched
    text3, corr3, unrec3 = correct_garbled_words(
        "I need a formal outfit for an interview, budget under 50"
    )
    assert text3 == "I need a formal outfit for an interview, budget under 50"
    assert corr3 == {} and unrec3 == []


def test_existing_occasion_flow_unaffected(deterministic):
    reqs, _, _ = fashion_requirement_service.process_request(
        "I need a formal outfit for an interview, budget under 50"
    )
    assert reqs.occasion == "interview"
    assert reqs.budget == 50.0
    assert not outfit_requirement_engine.clarification_needed(reqs)
    required, _ = outfit_requirement_engine.determine_requirements(reqs)
    assert required == ["top", "bottom", "footwear"]
