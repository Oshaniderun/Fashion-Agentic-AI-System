"""
Pandas-powered comparison of outfit options: ranked side-by-side table,
category-level price pivots, and savings analytics.
"""

import logging
from typing import Any, Dict, List

from shared.schemas.agent3_schemas import BudgetOptimizationResponse, OutfitOption

logger = logging.getLogger("budget_comparison")


def _get_pd():
    """Lazy pandas import — only needed when comparison endpoints are called."""
    try:
        import pandas as pd

        return pd
    except ImportError:
        raise RuntimeError("pandas is required for the comparison service.")


class ComparisonService:
    """DataFrame-based option comparison and savings rankings."""

    def build_comparison_table(
        self,
        options: List[OutfitOption],
        budget: float,
    ) -> List[Dict[str, Any]]:
        pd = _get_pd()

        rows = []
        for opt in options:
            cb = opt.cost_breakdown
            rows.append({
                "option_id": opt.combination_id,
                "strategy": opt.strategy.value,
                "name": opt.name,
                "total_cost_usd": cb.total_cost,
                "budget_usd": budget,
                "savings_usd": cb.savings_amount,
                "savings_pct": cb.savings_percentage,
                "budget_remaining_usd": cb.budget_remaining,
                "within_budget": opt.is_within_budget,
                "n_new_items": len(opt.selected_products),
                "n_wardrobe_reused": len(opt.wardrobe_items_used),
                "relevance_score": round(opt.relevance_score * 100, 1),
                "budget_efficiency": round(opt.budget_efficiency_score * 100, 1),
                "overall_value_score": round(opt.overall_value_score * 100, 1),
                "items_purchased": ", ".join(p.name for p in opt.selected_products) or "—",
                "stores": ", ".join({p.store or "?" for p in opt.selected_products}) or "—",
            })

        if not rows:
            return []

        df = pd.DataFrame(rows)
        df = df.sort_values("overall_value_score", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        return df.to_dict(orient="records")

    def build_category_breakdown(
        self,
        options: List[OutfitOption],
    ) -> Dict[str, Any]:
        pd = _get_pd()

        rows = []
        for opt in options:
            for p in opt.selected_products:
                rows.append({
                    "option": opt.name,
                    "category": p.category if isinstance(p.category, str) else p.category.value,
                    "product": p.name,
                    "price_usd": p.price,
                    "store": p.store or "Unknown",
                    "relevance": p.relevance_score,
                })

        if not rows:
            return {"categories": [], "summary": "No purchased products in any option."}

        df = pd.DataFrame(rows)
        summary = (
            df.groupby("category")["price_usd"]
            .agg(min_price="min", max_price="max", avg_price="mean", count="count")
            .reset_index()
            .round(2)
        )
        return {
            "categories": summary.to_dict(orient="records"),
            "all_products": df.to_dict(orient="records"),
        }

    def savings_ranking(self, options: List[OutfitOption]) -> List[Dict[str, Any]]:
        pd = _get_pd()
        rows = [
            {
                "name": o.name,
                "strategy": o.strategy.value,
                "savings_usd": o.cost_breakdown.savings_amount,
                "savings_pct": o.cost_breakdown.savings_percentage,
                "total_cost_usd": o.cost_breakdown.total_cost,
            }
            for o in options
        ]
        if not rows:
            return []
        df = pd.DataFrame(rows).sort_values("savings_usd", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        return df.to_dict(orient="records")

    def summary_stats(self, response: BudgetOptimizationResponse) -> Dict[str, Any]:
        pd = _get_pd()
        opts = response.options
        if not opts:
            return {"message": "No options available."}

        prices = [o.cost_breakdown.total_cost for o in opts]
        savings = [o.cost_breakdown.savings_percentage for o in opts]
        scores = [o.overall_value_score for o in opts]

        df_prices = pd.Series(prices)
        return {
            "n_options": len(opts),
            "budget_usd": response.budget_ceiling,
            "cheapest_usd": round(float(df_prices.min()), 2),
            "most_expensive_usd": round(float(df_prices.max()), 2),
            "avg_cost_usd": round(float(df_prices.mean()), 2),
            "max_savings_pct": round(max(savings), 1),
            "avg_savings_pct": round(sum(savings) / len(savings), 1),
            "best_value_score": round(max(scores) * 100, 1),
            "buy_nothing_available": response.buy_nothing_available,
            "status": response.status.value,
        }


_comparison_service = ComparisonService()


def get_comparison_service() -> ComparisonService:
    return _comparison_service
