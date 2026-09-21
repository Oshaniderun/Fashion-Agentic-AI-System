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

    # 3. Color extraction: excludes 'bright', infers preference for dark/neutral
    assert "bright" in reqs.excluded_colours
    assert any(c in reqs.colour_preferences for c in ["dark", "neutral"])

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
    assert "dark" in reqs.colour_preferences


def test_synonym_normalization():
    assert normalize_occasion("Heading to a wedding ceremony") == "wedding"
    assert normalize_occasion("Celebrating an engagement party tonight") == "engagement"
    assert normalize_occasion("Office client meeting") == "work"
    assert normalize_occasion("Tech hiring interview") == "interview"

    styles = normalize_styles("Keep it smart casual and chic")
    assert "smart_casual" in styles
    assert "elegant" in styles
