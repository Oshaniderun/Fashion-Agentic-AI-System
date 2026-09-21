"""
Missing Clothing Item Detection & Agent 2 Handoff Builder.
Compares required categories against owned wardrobe inventory to detect gaps.
"""

from typing import List, Dict, Any, Tuple
from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    Agent2SearchRequirement
)


class MissingItemDetector:
    """Identifies missing clothing categories to satisfy outfit requirements."""

    def analyze_missing(
        self,
        required_categories: List[str],
        optional_categories: List[str],
        owned_items: List[WardrobeSummaryItem],
        user_requirements: UserRequirements
    ) -> Tuple[OutfitRequirements, Agent2SearchRequirement]:
        """
        Determines available vs missing categories and structures the search payload for Agent 2.
        """
        # Set of categories currently present in user's wardrobe
        owned_categories = set(item.category.lower() for item in owned_items)

        available: List[str] = []
        missing: List[str] = []

        for req_cat in required_categories:
            cat_lower = req_cat.lower()
            # Normalize footwear/shoes equivalence
            if cat_lower in ["shoes", "footwear"]:
                if "shoes" in owned_categories or "footwear" in owned_categories:
                    available.append(req_cat)
                else:
                    missing.append(req_cat)
            else:
                if cat_lower in owned_categories:
                    available.append(req_cat)
                else:
                    missing.append(req_cat)

        outfit_reqs = OutfitRequirements(
            required_categories=required_categories,
            available_categories=available,
            missing_categories=missing,
            optional_categories=optional_categories
        )

        # Build clean search handoff for Agent 2
        # Synthesize expanded query text for Agent 2's BM25 & embedding search
        style_desc = " ".join(user_requirements.style) if user_requirements.style else "versatile"
        color_desc = " ".join(user_requirements.colour_preferences) if user_requirements.colour_preferences else "neutral"
        target_cats = " and ".join(missing) if missing else "accessories"
        occasion_desc = f"for {user_requirements.occasion}" if user_requirements.occasion else ""
        budget_desc = f"under LKR {int(user_requirements.budget)}" if user_requirements.budget else ""

        query_parts = [style_desc, color_desc, target_cats, occasion_desc, budget_desc]
        synthetic_query = " ".join([p for p in query_parts if p]).strip()

        search_handoff = Agent2SearchRequirement(
            missing_categories=missing,
            style=user_requirements.style,
            colour=user_requirements.colour_preferences,
            occasion=user_requirements.occasion,
            budget_remaining=user_requirements.budget,
            query_text=synthetic_query
        )

        return outfit_reqs, search_handoff


missing_item_detector = MissingItemDetector()
