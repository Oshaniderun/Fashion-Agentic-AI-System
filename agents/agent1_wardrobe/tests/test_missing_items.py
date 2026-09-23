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
    assert "footwear" in required_cats

    outfit_reqs, search_handoff, agent2_handoff = missing_item_detector.analyze_missing(
        required_categories=required_cats,
        optional_categories=optional_cats,
        owned_items=wardrobe,
        user_requirements=reqs,
        request_id="REQ-TEST-001",
    )

    assert "top" in outfit_reqs.available_categories
    assert "bottom" in outfit_reqs.available_categories
    assert "footwear" in outfit_reqs.missing_categories

    assert "footwear" in search_handoff.missing_categories
    assert "footwear" in search_handoff.categories
    assert search_handoff.occasion == "engagement"
    assert search_handoff.budget_remaining == 8000.0
    assert search_handoff.maximum_price == 8000.0
    assert "footwear" in search_handoff.query_text.lower()

    assert agent2_handoff.request_id == "REQ-TEST-001"
    assert "footwear" in agent2_handoff.wardrobe_status.missing_categories
    assert any(i.wardrobe_id == "W001" for i in agent2_handoff.available_items)


def test_interview_blouse_bottom_handoff_no_duplicate_bottom():
    wardrobe = [
        WardrobeSummaryItem(
            wardrobe_id="W001",
            category="top",
            type="blouse",
            colour="red",
            formality=0.7,
            style="formal",
        )
    ]
    reqs = UserRequirements(
        occasion="interview",
        style=["formal"],
        colour_preferences=[],
        budget=4000.0,
        requested_categories=["top", "bottom"],
        requested_types=["blouse", "bottom", "pant"],
    )
    required = ["top", "bottom"]
    outfit_reqs, search_handoff, handoff = missing_item_detector.analyze_missing(
        required_categories=required,
        optional_categories=[],
        owned_items=wardrobe,
        user_requirements=reqs,
        request_id="REQ-001",
    )
    assert outfit_reqs.missing_categories == ["bottom"]
    assert search_handoff.categories == ["bottom"]
    q = (search_handoff.query_text or "").lower()
    assert q.count("bottom") <= 1
    assert "blouse" not in q  # already owned — not for Agent 2 search
    assert handoff.available_items[0].colour == "red"
    assert handoff.search_requirements.maximum_price == 4000.0
