"""
Tests for Wardrobe Item Compatibility and Multi-Attribute Reasoning.
"""

from app.services.compatibility import compatibility_engine
from shared.schemas.agent1_schemas import UserRequirements, WardrobeSummaryItem


def test_black_blouse_blue_jeans_beige_loafers_compatibility():
    """
    Demonstrates Section 18 scenario:
    Black blouse (top, 0.70) + Blue jeans (bottom, 0.40) + Beige loafers (shoes, 0.65)
    Should evaluate to smart_casual, good color compatibility, moderate/high occasion suitability.
    """
    items = [
        WardrobeSummaryItem(
            wardrobe_id="W001",
            category="top",
            type="blouse",
            colour="black",
            formality=0.70,
            style="smart_casual"
        ),
        WardrobeSummaryItem(
            wardrobe_id="W002",
            category="bottom",
            type="jeans",
            colour="blue",
            formality=0.40,
            style="casual"
        ),
        WardrobeSummaryItem(
            wardrobe_id="W003",
            category="footwear",
            type="loafers",
            colour="beige",
            formality=0.65,
            style="smart_casual"
        ),
    ]

    reqs = UserRequirements(
        occasion="engagement",
        style=["elegant", "semi_formal"],
        colour_preferences=["dark", "neutral"],
        excluded_colours=["bright"],
        budget=8000.0
    )

    result = compatibility_engine.evaluate_outfit_combination(items, reqs)

    assert result.style in ["smart_casual", "semi_formal"]
    assert result.colour_compatibility in ["good", "excellent"]
    assert result.occasion_suitability in ["moderate", "high"]
    assert result.score >= 0.70
    assert len(result.explanation) > 20


def test_excluded_color_penalization():
    items = [
        WardrobeSummaryItem(
            wardrobe_id="W099",
            category="top",
            type="shirt",
            colour="bright yellow",
            formality=0.5,
            style="casual"
        )
    ]
    reqs = UserRequirements(
        occasion="engagement",
        style=["elegant"],
        colour_preferences=["dark"],
        excluded_colours=["bright"],
        budget=5000.0
    )

    result = compatibility_engine.evaluate_outfit_combination(items, reqs)
    assert result.colour_compatibility == "clashing"
    assert "matches user-excluded" in result.explanation
