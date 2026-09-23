"""
Tests for NLP Requirement Extraction, Synonym Normalization, and Uncertainty Preservation.
"""

from app.services.nlp.requirement_extractor import fashion_requirement_service
from app.services.nlp.normalization import (
    normalize_occasion,
    normalize_styles,
    extract_color_preferences_and_exclusions,
    extract_budget,
)


def test_section_50_primary_demo_request():
    """
    Demonstrates the exact scenario required by Section 50:
    'I need something elegant but not too formal for my cousin's engagement. I don't want bright colours.'
    """
    prompt = "I need something elegant but not too formal for my cousin's engagement. I don't want bright colours."
    reqs, conf, threat = fashion_requirement_service.process_request(prompt)

    # 1. Occasion extraction
    assert reqs.occasion == "engagement"

    # 2. Style extraction: 'elegant' and 'not too formal' -> 'semi_formal'
    assert "elegant" in reqs.style
    assert "semi_formal" in reqs.style

    # 3. Color extraction:
    #    - User EXPLICITLY excluded 'bright' -> must appear in excluded_colours
    #    - User did NOT state any positive preference -> colour_preferences must be EMPTY
    #    (auto-inferring dark/neutral from bright exclusion is a bug: user didn't say that)
    assert "bright" in reqs.excluded_colours
    assert reqs.colour_preferences == [] or reqs.colour_preferences is None

    # 4. Uncertainty preservation: budget was not mentioned, must NOT be hallucinated
    assert reqs.budget is None

    # 5. Security threat score should be clean
    assert threat.is_safe is True
    assert threat.risk_score == 0.0


def test_budget_extraction_and_currency_variants():
    # Number with 'around'
    p1 = "I need a formal outfit for an interview and can spend around 8000."
    reqs1, _, _ = fashion_requirement_service.process_request(p1)
    assert reqs1.budget == 8000.0
    assert reqs1.occasion == "interview"
    assert "formal" in reqs1.style

    # Currency prefix 'LKR 10,000'
    p2 = "University presentation outfit, budget LKR 10,000."
    reqs2, _, _ = fashion_requirement_service.process_request(p2)
    assert reqs2.budget == 10000.0
    assert reqs2.occasion == "university"


def test_uncertainty_preservation_no_hallucinations():
    # Prompt without occasion or budget
    p = "Find me a dark jacket for tomorrow."
    reqs, _, _ = fashion_requirement_service.process_request(p)
    assert reqs.occasion is None
    assert reqs.budget is None
    # "dark" should be bound to the jacket item, not a global preference
    assert reqs.colour_preferences == []
    assert len(reqs.identified_items) > 0
    assert reqs.identified_items[0].colour == "dark"
    assert reqs.identified_items[0].type == "jacket"


def test_synonym_normalization():
    assert normalize_occasion("Heading to a wedding ceremony") == "wedding"
    assert normalize_occasion("Celebrating an engagement party tonight") == "engagement"
    assert normalize_occasion("Office client meeting") == "work"
    assert normalize_occasion("Tech hiring interview") == "interview"

    styles = normalize_styles("Keep it smart casual and chic")
    assert "smart_casual" in styles
    assert "elegant" in styles


def test_checked_frock_extracts_pattern_in_handoff():
    from app.services.outfit_requirements import outfit_requirement_engine
    from app.services.missing_items import missing_item_detector

    prompt = "I need some checked design frock"
    reqs, _, _ = fashion_requirement_service.process_request(prompt)
    assert "dress" in reqs.requested_categories
    assert "checked" in reqs.pattern_preferences

    required, optional = outfit_requirement_engine.determine_requirements(reqs)
    assert required == ["dress"]

    _, handoff, full = missing_item_detector.analyze_missing(
        required_categories=required,
        optional_categories=optional,
        owned_items=[],
        user_requirements=reqs,
        request_id="REQ-FROCK",
    )
    assert "checked" in handoff.pattern
    assert "checked" in handoff.pattern_preferences
    assert "checked" in (handoff.query_text or "").lower()
    assert "frock" in (handoff.query_text or "").lower() or "dress" in (handoff.query_text or "").lower()
    assert full.search_requirements.categories == handoff.categories


def test_item_role_black_heel_exclusion():
    """
    User requests a blouse and pant, and mentions a 'black heel'.
    If the wardrobe already has a black heel, the Agent 2 query should NOT contain 'black' or 'heel'.
    """
    from app.services.outfit_requirements import outfit_requirement_engine
    from app.services.missing_items import missing_item_detector
    from shared.schemas.agent1_schemas import WardrobeSummaryItem

    prompt = "I need something formal for an interview like a blouse and a bottom pant with a black heel"
    reqs, _, _ = fashion_requirement_service.process_request(prompt)

    # NLP should correctly associate 'black' to 'heel', not globally
    assert "black" not in reqs.colour_preferences
    assert any(it.colour == "black" and it.type == "heel" for it in reqs.identified_items)

    # Provide the wardrobe with black heels
    owned_items = [
        WardrobeSummaryItem(
            wardrobe_id="W007", category="footwear", type="heels", colour="black", pattern="solid", style="formal"
        ),
        WardrobeSummaryItem(
            wardrobe_id="W003", category="top", type="blouse", colour="red", pattern="solid", style="formal"
        )
    ]
    
    required, optional = outfit_requirement_engine.determine_requirements(reqs)
    _, handoff, _ = missing_item_detector.analyze_missing(
        required_categories=required,
        optional_categories=optional,
        owned_items=owned_items,
        user_requirements=reqs,
    )
    
    query = (handoff.query_text or "").lower()
    assert "pant" in query
    # "heel" and "black" belong to the owned item, not the missing one
    assert "heel" not in query
    assert "black" not in query


def test_item_role_ownership_context():
    """
    User says: 'I have blue jeans and a white shirt, I need a matching jacket'
    Jeans and shirt should be 'existing', jacket should be 'requested'.
    """
    prompt = "I have blue jeans and a white shirt, I need a matching jacket"
    reqs, _, _ = fashion_requirement_service.process_request(prompt)
    
    jeans = next((it for it in reqs.identified_items if it.type == "jeans"), None)
    shirt = next((it for it in reqs.identified_items if it.type == "shirt"), None)
    jacket = next((it for it in reqs.identified_items if it.type == "jacket"), None)
    
    assert jeans is not None and jeans.role == "existing_reference" and jeans.colour == "blue"
    assert shirt is not None and shirt.role == "existing_reference" and shirt.colour == "white"
    assert jacket is not None and jacket.role == "requested"


def test_item_role_backward_compatibility():
    """Simple requests with no ownership context default to 'requested'."""
    prompt = "I need a blue blouse and formal pant"
    reqs, _, _ = fashion_requirement_service.process_request(prompt)
    
    blouse = next((it for it in reqs.identified_items if it.type == "blouse"), None)
    pant = next((it for it in reqs.identified_items if it.type == "pant"), None)
    
    assert blouse is not None and blouse.role == "requested" and blouse.colour == "blue"
    assert pant is not None and pant.role == "requested"
