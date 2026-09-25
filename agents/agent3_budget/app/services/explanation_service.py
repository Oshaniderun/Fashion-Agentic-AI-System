"""
Deterministic explanation service (FASHORA budget planner).

Plain-language, transparent justifications for financial decisions.
Money math is never delegated to an LLM — this module is the source of
truth for explanation text, and the Gemini polish layer falls back to it.
"""

from typing import List

from shared.schemas.agent3_schemas import (
    CandidateProductItem,
    CostBreakdown,
    OptimizationStrategy,
)


class ExplanationService:
    """Produces explainable, transparent financial trade-off rationales."""

    def generate_explanation(
        self,
        strategy: OptimizationStrategy,
        selected_products: List[CandidateProductItem],
        cost_breakdown: CostBreakdown,
        relevance_score: float,
    ) -> str:
        ceiling = cost_breakdown.budget_ceiling
        total = cost_breakdown.total_cost
        remaining = cost_breakdown.budget_remaining
        savings_pct = cost_breakdown.savings_percentage

        if strategy == OptimizationStrategy.BUY_NOTHING:
            return (
                "Sustainable Zero-Spend Option: uses your owned wardrobe items to avoid any "
                f"commercial purchase. Achieves 100% budget savings (preserving USD {ceiling:,.2f})."
            )

        item_names = [f"{p.name} (USD {p.price:,.2f})" for p in selected_products]
        items_str = ", ".join(item_names) if item_names else "no new purchases"

        if strategy == OptimizationStrategy.MINIMAL_PURCHASE:
            return (
                f"Minimal Purchase Strategy: acquires only the highest-priority item ({items_str}) "
                f"costing USD {total:,.2f}. This saves USD {remaining:,.2f} "
                f"({savings_pct:.1f}% of your budget) while styling the rest of the outfit "
                "with your existing wardrobe."
            )

        if strategy == OptimizationStrategy.BEST_VALUE:
            return (
                f"Best Value Strategy: balances retrieval relevance ({relevance_score * 100:.0f}%) "
                f"against cost efficiency. Total expenditure is USD {total:,.2f}, leaving a safe "
                f"financial buffer of USD {remaining:,.2f} ({savings_pct:.1f}% savings) under your "
                f"USD {ceiling:,.2f} ceiling."
            )

        if strategy == OptimizationStrategy.TOP_MATCH:
            return (
                f"Top Match Strategy: selects the highest quality candidate items ({items_str}) "
                f"with a top relevance score of {relevance_score * 100:.0f}%. Total cost is "
                f"USD {total:,.2f}, remaining within your USD {ceiling:,.2f} budget."
            )

        return (
            f"Selected items: {items_str}. Total cost is USD {total:,.2f} with "
            f"USD {remaining:,.2f} remaining from your USD {ceiling:,.2f} budget."
        )


_explanation_service = ExplanationService()


def get_explanation_service() -> ExplanationService:
    return _explanation_service
