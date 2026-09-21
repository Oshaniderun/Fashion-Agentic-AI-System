"""
Outfit Compatibility and Harmony Reasoning Engine.
Evaluates color harmony, style consistency, formality alignment, and occasion suitability.
Provides transparent, explainable scores grounded in fashion design principles.
"""

from typing import List, Dict, Any, Tuple, Optional
from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    CompatibilityDetails
)

# Complementary and harmonious color pairings
NEUTRAL_COLORS = {"black", "white", "grey", "navy", "beige", "brown"}

OCCASION_EXPECTED_FORMALITY = {
    "wedding": 0.85,
    "formal_event": 0.85,
    "interview": 0.80,
    "work": 0.70,
    "engagement": 0.65,
    "dinner": 0.65,
    "university": 0.45,
    "party": 0.50,
    "casual": 0.35,
}


class CompatibilityEngine:
    """Computes explainable compatibility between owned items and user intent."""

    def evaluate_outfit_combination(
        self,
        candidate_items: List[WardrobeSummaryItem],
        requirements: UserRequirements
    ) -> CompatibilityDetails:
        """
        Calculates color harmony, style consistency, and occasion suitability
        for the given set of wardrobe items.
        """
        if not candidate_items:
            return CompatibilityDetails(
                style="casual",
                occasion_suitability="low",
                colour_compatibility="moderate",
                score=0.40,
                explanation="No wardrobe items were selected to evaluate compatibility."
            )

        # 1. Colour compatibility analysis
        colors = [item.colour.lower() for item in candidate_items]
        color_score, color_rating, color_reason = self._evaluate_colors(colors, requirements)

        # 2. Formality & Style alignment
        formalities = [item.formality for item in candidate_items]
        avg_formality = sum(formalities) / len(formalities)
        formality_spread = max(formalities) - min(formalities) if len(formalities) > 1 else 0.0

        # Penalize large formality spread (e.g. formal blazer + beach flip flops)
        style_consistency = max(0.5, 1.0 - (formality_spread * 0.7))

        # 3. Occasion suitability
        target_occasion = (requirements.occasion or "casual").lower()
        expected_formality = OCCASION_EXPECTED_FORMALITY.get(target_occasion, 0.50)
        occasion_delta = abs(avg_formality - expected_formality)
        occasion_score = max(0.3, 1.0 - (occasion_delta * 1.2))

        if occasion_score >= 0.80:
            occ_rating = "high"
        elif occasion_score >= 0.55:
            occ_rating = "moderate"
        else:
            occ_rating = "low"

        # Synthesize overall style label
        if avg_formality >= 0.75:
            overall_style = "formal"
        elif avg_formality >= 0.55:
            overall_style = "smart_casual"
        elif avg_formality >= 0.40:
            overall_style = "semi_formal"
        else:
            overall_style = "casual"

        # Overall composite score
        # 0.35 * color + 0.35 * occasion + 0.30 * style consistency
        overall_score = round(float((0.35 * color_score) + (0.35 * occasion_score) + (0.30 * style_consistency)), 2)

        # Human-readable, transparent explanation
        item_names = [f"{item.colour} {item.type}" for item in candidate_items]
        items_str = " + ".join(item_names)
        
        explanation = (
            f"This combination ({items_str}) achieves a {overall_style.replace('_', ' ')} aesthetic. "
            f"{color_reason} The average formality level ({round(avg_formality, 2)}) demonstrates "
            f"{occ_rating} suitability for an {target_occasion} setting."
        )

        return CompatibilityDetails(
            style=overall_style,
            occasion_suitability=occ_rating,
            colour_compatibility=color_rating,
            score=overall_score,
            explanation=explanation
        )

    def _evaluate_colors(
        self,
        colors: List[str],
        requirements: UserRequirements
    ) -> Tuple[float, str, str]:
        """Evaluates color palette harmony and user exclusion adherence."""
        # Check against user excluded colors
        for col in colors:
            for exc in requirements.excluded_colours:
                if exc in col:
                    return 0.40, "clashing", f"Item color '{col}' matches user-excluded color preference '{exc}'."

        # Neutrals pairing rule: all neutrals or neutrals + 1 accent color is good harmony
        neutral_count = sum(1 for c in colors if c in NEUTRAL_COLORS)
        non_neutral_count = len(colors) - neutral_count

        if non_neutral_count <= 1:
            return 0.95, "excellent", "Neutral color palette creates balanced and versatile harmony."
        elif non_neutral_count == 2:
            return 0.85, "good", "Cohesive color balance with complementary tones."
        else:
            return 0.65, "moderate", "Multi-color combination with varied tonal contrast."


compatibility_engine = CompatibilityEngine()
