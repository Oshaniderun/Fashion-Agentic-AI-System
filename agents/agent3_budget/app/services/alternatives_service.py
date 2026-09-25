"""
Feedback Loop & Alternatives Service.
Computes cheaper-alternative directives for Agent 2 when combinations
exceed the budget ceiling.
"""

from typing import Dict, List

from shared.schemas.agent3_schemas import (
    CandidateProductItem,
    FeedbackLoopRecommendation,
)


class AlternativesService:
    """Category-level price ceilings and feedback directives for Agent 2."""

    def analyze_budget_overrun(
        self,
        budget_ceiling: float,
        candidate_products_by_category: Dict[str, List[CandidateProductItem]],
    ) -> List[FeedbackLoopRecommendation]:
        """Targets per category so Agent 2 can retry with a lower price ceiling."""
        if not candidate_products_by_category:
            return []

        recommendations: List[FeedbackLoopRecommendation] = []
        category_min_prices: Dict[str, float] = {}

        for cat, items in candidate_products_by_category.items():
            if items:
                category_min_prices[cat] = min(p.price for p in items)
            else:
                category_min_prices[cat] = 0.0

        total_min_cost = sum(category_min_prices.values())
        num_categories = max(1, len(category_min_prices))

        if total_min_cost > budget_ceiling:
            for cat, min_price in category_min_prices.items():
                if total_min_cost > 0:
                    weight = min_price / total_min_cost
                else:
                    weight = 1.0 / num_categories

                target_ceiling = round(budget_ceiling * weight, 2)

                overage_pct = ((min_price - target_ceiling) / max(1.0, target_ceiling)) * 100
                if overage_pct > 30:
                    action = "request_cheaper_alternatives"
                    note = (
                        f"Current cheapest item (USD {min_price:,.2f}) is {overage_pct:.0f}% above "
                        "target. Recommend widening the price search to mass-market brands."
                    )
                else:
                    action = "relax_colour_or_brand"
                    note = (
                        f"Target price ceiling of USD {target_ceiling:,.2f} required to fit the "
                        f"overall USD {budget_ceiling:,.2f} budget."
                    )

                recommendations.append(
                    FeedbackLoopRecommendation(
                        category=cat,
                        current_lowest_price=min_price,
                        target_max_price=target_ceiling,
                        action=action,
                        suggested_query_notes=note,
                    )
                )

        return recommendations


_alternatives_service = AlternativesService()


def get_alternatives_service() -> AlternativesService:
    return _alternatives_service
