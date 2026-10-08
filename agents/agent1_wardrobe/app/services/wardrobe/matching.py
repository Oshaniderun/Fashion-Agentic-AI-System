"""
Wardrobe Matching and Outfit Candidate Selection Service.
"""

from typing import List, Dict
from app.services.item_match import constraints_for_category, item_satisfies
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
            constraints = constraints_for_category(requirements, cat_lower)
            candidates = [it for it in candidates if item_satisfies(it, constraints)]

            if candidates:
                # Rank candidates by score
                best_item = max(candidates, key=lambda it: self._score_item(it, requirements))
                
                # Overwrite confidence with the match score so the frontend shows how well it matched
                match_score = self._score_item(best_item, requirements)
                # Create a copy so we don't mutate the original item which might be used elsewhere
                best_item_copy = best_item.model_copy()
                best_item_copy.confidence = match_score
                
                selected_candidates.append(best_item_copy)

        return selected_candidates

    def _score_item(self, item: WardrobeSummaryItem, requirements: UserRequirements) -> float:
        """Scores an individual item's alignment with user requirements."""
        score = 0.55

        item_colour = (item.colour or "").lower()
        item_style = (item.style or "").lower()
        item_cat = (item.category or "").lower()

        # 1. Global style or occasion formality alignment bonus
        style_match = any(s.lower() in item_style for s in (requirements.style or []))
        formality_match = False
        if requirements.occasion:
            occ = requirements.occasion.lower()
            if occ in ["interview", "formal_event", "wedding", "work"]:
                formality_match = item_style in ["formal", "smart_casual", "business"] or item.formality >= 0.60
            elif occ in ["party", "dinner", "engagement"]:
                formality_match = item_style in ["semi_formal", "smart_casual", "elegant"] or item.formality >= 0.50
            elif occ in ["university", "casual"]:
                formality_match = True

        if style_match or formality_match:
            score += 0.25

        # 2. Color match bonus (from global preferences OR item-specific identified items)
        global_color_match = any(c.lower() in item_colour for c in (requirements.colour_preferences or []))
        item_specific_color_match = False
        if requirements.identified_items:
            for ref in requirements.identified_items:
                ref_cat = (ref.category or "").lower()
                ref_col = (ref.colour or "").lower()
                if ref_col and (ref_cat == item_cat or ref_cat in item_cat or item_cat in ref_cat):
                    if ref_col in item_colour or item_colour in ref_col:
                        item_specific_color_match = True
                        break

        if global_color_match or item_specific_color_match:
            score += 0.20

        # 3. Versatile neutral color bonus
        if item_colour in ["black", "white", "grey", "beige", "navy", "cream", "brown"]:
            score += 0.10

        return min(0.95, round(score, 2))


wardrobe_matcher = WardrobeMatcher()
