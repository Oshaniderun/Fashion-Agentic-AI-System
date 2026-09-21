"""
Wardrobe Matching and Outfit Candidate Selection Service.
"""

from typing import List, Dict, Any, Tuple
from shared.schemas.agent1_schemas import UserRequirements, WardrobeSummaryItem


class WardrobeMatcher:
    """Matches owned wardrobe items to outfit requirements."""

    def select_compatible_items(
        self,
        wardrobe: List[WardrobeSummaryItem],
        requirements: UserRequirements,
        required_categories: List[str]
    ) -> List[WardrobeSummaryItem]:
        """
        Selects best-matching owned wardrobe items for the requested outfit.
        Prioritizes items avoiding excluded colors, matching styles, and covering required categories.
        """
        if not wardrobe:
            return []

        # Filter out any items in user-excluded colors
        viable_items = []
        for item in wardrobe:
            is_excluded = any(exc in item.colour.lower() for exc in requirements.excluded_colours)
            if not is_excluded:
                viable_items.append(item)

        if not viable_items:
            viable_items = wardrobe  # fallback if all items excluded

        # Group by category
        by_cat: Dict[str, List[WardrobeSummaryItem]] = {}
        for item in viable_items:
            by_cat.setdefault(item.category.lower(), []).append(item)

        selected_candidates: List[WardrobeSummaryItem] = []

        # For each required category, pick the best matching item
        for cat in required_categories:
            cat_lower = cat.lower()
            candidates = by_cat.get(cat_lower, [])
            if not candidates and cat_lower in ["shoes", "footwear"]:
                candidates = by_cat.get("shoes", []) or by_cat.get("footwear", [])

            if candidates:
                # Rank candidates by score
                best_item = max(candidates, key=lambda it: self._score_item(it, requirements))
                selected_candidates.append(best_item)

        return selected_candidates

    def _score_item(self, item: WardrobeSummaryItem, requirements: UserRequirements) -> float:
        """Scores an individual item's alignment with user requirements."""
        score = 0.5

        # Style match bonus
        if any(s in item.style.lower() for s in requirements.style):
            score += 0.3

        # Color match bonus
        if any(c in item.colour.lower() for c in requirements.colour_preferences):
            score += 0.2

        # Neutral color versatility bonus
        if item.colour.lower() in ["black", "white", "grey", "beige", "navy"]:
            score += 0.1

        return score


wardrobe_matcher = WardrobeMatcher()
