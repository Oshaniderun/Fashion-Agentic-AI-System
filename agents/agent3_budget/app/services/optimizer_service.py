"""
Combinatorial optimization engine for budget-constrained outfit selection.

All money math is deterministic here — the LLM is only ever used downstream
for narrative explanations, never for computing costs.
"""

import itertools
import logging
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.services.alternatives_service import get_alternatives_service
from app.services.buy_nothing_service import WardrobeFitCriteria, get_buy_nothing_service
from app.services.explanation_service import get_explanation_service
from shared.schemas.agent1_schemas import WardrobeSummaryItem
from shared.schemas.agent3_schemas import (
    BudgetOptimizationRequest,
    BudgetOptimizationResponse,
    BudgetStatus,
    CandidateProductItem,
    CostBreakdown,
    OptimizationStrategy,
    OutfitOption,
    WardrobeRepurposedItem,
)

logger = logging.getLogger("budget_optimizer")
settings = get_settings()

TOP_K_PER_CATEGORY = 15  # caps combinatorial explosion


class BudgetOptimizerService:
    """Multi-tier strategy generation under a hard budget ceiling."""

    def __init__(self):
        self.buy_nothing_service = get_buy_nothing_service()
        self.alternatives_service = get_alternatives_service()
        self.explanation_service = get_explanation_service()

    def optimize(self, request: BudgetOptimizationRequest) -> BudgetOptimizationResponse:
        budget = request.budget
        missing_categories = [c.lower().strip() for c in request.missing_categories]
        excluded_ids: Set[str] = set(request.excluded_product_ids or [])
        wardrobe = request.available_wardrobe or []
        max_prices = request.max_price_per_category or {}
        criteria = WardrobeFitCriteria.from_request(
            compatible_ids=[str(i) for i in request.compatible_wardrobe_ids],
            preferred_colours=[c.lower().strip() for c in request.preferred_colours],
            excluded_colours=[c.lower().strip() for c in request.excluded_colours],
            styles=[s.lower().strip().replace(" ", "_") for s in request.requested_styles],
        )

        # Wardrobe already satisfies every requirement
        if not missing_categories:
            buy_nothing_opt = self.buy_nothing_service.assemble_buy_nothing_option(
                budget_ceiling=budget,
                missing_categories=[],
                available_wardrobe=wardrobe,
                style_categories=[c.lower().strip() for c in request.outfit_categories],
                criteria=criteria,
            )
            options = [buy_nothing_opt] if buy_nothing_opt else []
            return BudgetOptimizationResponse(
                request_id=request.request_id,
                status=BudgetStatus.NO_PURCHASE_NEEDED,
                budget_ceiling=budget,
                budget_source=request.budget_source,
                options=options,
                recommended_option_id=options[0].combination_id if options else None,
                buy_nothing_available=bool(buy_nothing_opt),
                cheapest_combination_cost=0.0,
                notes=(
                    "Your existing wardrobe already satisfies all outfit requirements. "
                    "No purchase necessary."
                ),
            )

        # 1. Filter / organize candidates per category
        filtered_candidates: Dict[str, List[CandidateProductItem]] = {}
        for cat in missing_categories:
            raw_items = request.candidate_products_by_category.get(cat, [])
            cat_cap = max_prices.get(cat)

            valid_items: List[CandidateProductItem] = []
            for item in raw_items:
                if item.product_id in excluded_ids:
                    continue
                if cat_cap is not None and item.price > cat_cap:
                    continue
                valid_items.append(item)

            valid_items.sort(key=lambda p: (-p.relevance_score, p.price))
            filtered_candidates[cat] = valid_items

        categories_with_candidates = [
            cat for cat in missing_categories if filtered_candidates.get(cat)
        ]

        # 2. Explore combinations (only when every category has candidates)
        feasible_combinations: List[Tuple[Tuple[CandidateProductItem, ...], float, float]] = []
        infeasible_combinations: List[Tuple[Tuple[CandidateProductItem, ...], float, float]] = []

        if len(categories_with_candidates) == len(missing_categories):
            candidate_lists = [
                filtered_candidates[cat][:TOP_K_PER_CATEGORY] for cat in missing_categories
            ]

            for combo in itertools.product(*candidate_lists):
                total_cost = sum(p.price for p in combo)
                avg_relevance = sum(p.relevance_score for p in combo) / len(combo)

                if total_cost <= budget:
                    feasible_combinations.append((combo, total_cost, avg_relevance))
                else:
                    infeasible_combinations.append((combo, total_cost, avg_relevance))

        # 3. Strategic outfit options
        options: List[OutfitOption] = []

        # Strategy A: Buy Nothing (zero spend from owned wardrobe)
        buy_nothing_opt = self.buy_nothing_service.assemble_buy_nothing_option(
            budget_ceiling=budget,
            missing_categories=missing_categories,
            available_wardrobe=wardrobe,
            criteria=criteria,
        )
        if buy_nothing_opt:
            options.append(buy_nothing_opt)

        # Strategy B: Best Value — maximize 0.6*relevance + 0.4*(1 - cost/budget)
        best_value_opt = None
        if feasible_combinations:
            best_value_tuple = max(
                feasible_combinations,
                key=lambda x: (0.6 * x[2]) + (0.4 * (1.0 - (x[1] / max(1.0, budget)))),
            )
            best_value_opt = self._build_option(
                combination_id="OPT-BEST-VALUE",
                strategy=OptimizationStrategy.BEST_VALUE,
                name="Best Value Outfit",
                products=list(best_value_tuple[0]),
                total_cost=best_value_tuple[1],
                budget_ceiling=budget,
                avg_relevance=best_value_tuple[2],
                wardrobe=wardrobe,
                missing_categories=missing_categories,
                criteria=criteria,
            )
            options.append(best_value_opt)

        # Strategy C: Top Match — highest relevance within budget (if distinct)
        top_match_opt = None
        if feasible_combinations:
            top_match_tuple = max(
                feasible_combinations,
                key=lambda x: (x[2], -x[1]),
            )
            if not best_value_opt or set(p.product_id for p in top_match_tuple[0]) != set(
                p.product_id for p in best_value_opt.selected_products
            ):
                top_match_opt = self._build_option(
                    combination_id="OPT-TOP-MATCH",
                    strategy=OptimizationStrategy.TOP_MATCH,
                    name="Top Quality / Match Outfit",
                    products=list(top_match_tuple[0]),
                    total_cost=top_match_tuple[1],
                    budget_ceiling=budget,
                    avg_relevance=top_match_tuple[2],
                    wardrobe=wardrobe,
                    missing_categories=missing_categories,
                    criteria=criteria,
                )
                options.append(top_match_opt)

        # Strategy D: Minimal Purchase — only the primary essential item
        if len(missing_categories) > 1 and categories_with_candidates:
            primary_cat = missing_categories[0]
            if filtered_candidates.get(primary_cat):
                cheapest_primary = filtered_candidates[primary_cat][0]
                if cheapest_primary.price <= budget:
                    minimal_opt = self._build_option(
                        combination_id="OPT-MINIMAL-PURCHASE",
                        strategy=OptimizationStrategy.MINIMAL_PURCHASE,
                        name="Minimal Purchase Outfit",
                        products=[cheapest_primary],
                        total_cost=cheapest_primary.price,
                        budget_ceiling=budget,
                        avg_relevance=cheapest_primary.relevance_score,
                        wardrobe=wardrobe,
                        missing_categories=missing_categories,
                        criteria=criteria,
                    )
                    options.append(minimal_opt)

        # 4. Status + feedback-loop directives
        feedback_recommendations = []
        cheapest_cost = None

        if feasible_combinations:
            status = BudgetStatus.WITHIN_BUDGET
            cheapest_cost = min(c[1] for c in feasible_combinations)
            recommended_id = (
                best_value_opt.combination_id if best_value_opt else options[0].combination_id
            )
            notes = (
                f"Found {len(feasible_combinations)} feasible combination(s) strictly within "
                f"your USD {budget:,.2f} budget."
            )
        elif options:
            status = BudgetStatus.PARTIALLY_FEASIBLE
            feedback_recommendations = self.alternatives_service.analyze_budget_overrun(
                budget_ceiling=budget,
                candidate_products_by_category=filtered_candidates,
            )
            recommended_id = options[0].combination_id
            notes = (
                f"Full new-product combinations exceed your USD {budget:,.2f} budget. However, "
                f"{len(options)} sustainable / partial wardrobe option(s) are feasible."
            )
        else:
            status = BudgetStatus.EXCEEDS_BUDGET
            feedback_recommendations = self.alternatives_service.analyze_budget_overrun(
                budget_ceiling=budget,
                candidate_products_by_category=filtered_candidates,
            )
            if infeasible_combinations:
                cheapest_cost = min(c[1] for c in infeasible_combinations)
            recommended_id = None
            notes = (
                f"All candidate product combinations exceed your budget ceiling of "
                f"USD {budget:,.2f}. Cheapest combination requires USD {cheapest_cost or 0:,.2f}. "
                "Cheaper-alternative directives are available for a retrieval retry."
            )

        return BudgetOptimizationResponse(
            request_id=request.request_id,
            status=status,
            budget_ceiling=budget,
            budget_source=request.budget_source,
            options=options,
            recommended_option_id=recommended_id,
            buy_nothing_available=bool(buy_nothing_opt),
            cheapest_combination_cost=cheapest_cost,
            feedback_loop_recommendations=feedback_recommendations,
            notes=notes,
        )

    def _build_option(
        self,
        combination_id: str,
        strategy: OptimizationStrategy,
        name: str,
        products: List[CandidateProductItem],
        total_cost: float,
        budget_ceiling: float,
        avg_relevance: float,
        wardrobe: List[WardrobeSummaryItem],
        missing_categories: List[str],
        criteria: Optional[WardrobeFitCriteria] = None,
    ) -> OutfitOption:
        purchased_categories = {p.category.lower().strip() for p in products}
        still_needed = [c for c in missing_categories if c not in purchased_categories]
        repurposed_wardrobe: List[WardrobeRepurposedItem] = [
            WardrobeRepurposedItem(
                wardrobe_id=w.wardrobe_id,
                category=w.category,
                type=w.type,
                colour=w.colour,
                repurpose_role=f"Owned wardrobe base ({w.colour} {w.type})",
                cost=0.0,
            )
            for _cat, w in self.buy_nothing_service.select_replacements(
                still_needed, wardrobe, criteria=criteria
            )
        ]

        remaining = round(budget_ceiling - total_cost, 2)
        savings_amount = max(0.0, remaining)
        savings_pct = round((savings_amount / max(1.0, budget_ceiling)) * 100, 2)

        cost_per_cat = {p.category: p.price for p in products}

        cost_breakdown = CostBreakdown(
            total_cost=round(total_cost, 2),
            budget_ceiling=budget_ceiling,
            budget_remaining=remaining,
            savings_amount=savings_amount,
            savings_percentage=savings_pct,
            cost_per_category=cost_per_cat,
        )

        budget_efficiency = round(
            max(0.0, min(1.0, 0.5 + 0.5 * (remaining / max(1.0, budget_ceiling)))), 2
        )
        overall_value = round((0.6 * avg_relevance) + (0.4 * budget_efficiency), 2)

        explanation = self.explanation_service.generate_explanation(
            strategy=strategy,
            selected_products=products,
            cost_breakdown=cost_breakdown,
            relevance_score=avg_relevance,
        )

        item_titles = [f"{p.name} (USD {p.price:,.2f})" for p in products]
        desc = f"{name}: {', '.join(item_titles)} with {len(repurposed_wardrobe)} wardrobe pieces."

        return OutfitOption(
            combination_id=combination_id,
            strategy=strategy,
            name=name,
            description=desc,
            selected_products=products,
            wardrobe_items_used=repurposed_wardrobe,
            cost_breakdown=cost_breakdown,
            budget_efficiency_score=budget_efficiency,
            relevance_score=round(avg_relevance, 2),
            overall_value_score=overall_value,
            is_within_budget=(total_cost <= budget_ceiling),
            financial_explanation=explanation,
        )


_optimizer_service = BudgetOptimizerService()


def get_optimizer_service() -> BudgetOptimizerService:
    return _optimizer_service
