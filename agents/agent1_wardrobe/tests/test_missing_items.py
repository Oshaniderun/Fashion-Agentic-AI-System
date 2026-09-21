"""
Tests for Outfit Requirements and Missing Item Detection.
"""

from app.services.outfit_requirements import outfit_requirement_engine
from app.services.missing_items import missing_item_detector
from shared.schemas.agent1_schemas import UserRequirements, WardrobeSummaryItem


def test_missing_shoes_detection_scenario():
    # User owns black blouse (top) and blue jeans (bottom)
    wardrobe = [
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
        )
    ]

    reqs = UserRequirements(
        occasion="engagement",
        style=["elegant", "semi_formal"],
        colour_preferences=["dark", "neutral"],
        excluded_colours=["bright"],
        budget=8000.0
    )

    required_cats, optional_cats = outfit_requirement_engine.determine_requirements(reqs)
    assert "top" in required_cats
    assert "bottom" in required_cats
    assert "shoes" in required_cats

    outfit_reqs, search_handoff = missing_item_detector.analyze_missing(
        required_categories=required_cats,
        optional_categories=optional_cats,
        owned_items=wardrobe,
        user_requirements=reqs
    )

    assert "top" in outfit_reqs.available_categories
    assert "bottom" in outfit_reqs.available_categories
    assert "shoes" in outfit_reqs.missing_categories

    # Verify handoff payload for Agent 2
    assert "shoes" in search_handoff.missing_categories
    assert search_handoff.occasion == "engagement"
    assert search_handoff.budget_remaining == 8000.0
    assert "shoes" in search_handoff.query_text.lower()
