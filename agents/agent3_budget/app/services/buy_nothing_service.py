"""
Buy Nothing Mode & Wardrobe Repurposing Service.
FASHORA's sustainable, wardrobe-first purchase minimization strategy.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from shared.schemas.agent1_schemas import WardrobeSummaryItem
from shared.schemas.agent3_schemas import (
    CostBreakdown,
    OptimizationStrategy,
    OutfitOption,
    WardrobeRepurposedItem,
)


@dataclass(frozen=True)
class WardrobeFitCriteria:
    """Compatibility signals from Agent 1 used to filter/rank owned items.

    When enforce=True an item must carry at least one real signal
    (Agent 1 compatibility, requested colour, or requested style) to be
    shown; same-category-only items are hidden."""

    compatible_ids: FrozenSet[str] = frozenset()
    preferred_colours: FrozenSet[str] = frozenset()
    excluded_colours: FrozenSet[str] = frozenset()
    styles: FrozenSet[str] = frozenset()
    enforce: bool = False

    @classmethod
    def from_request(
        cls,
        compatible_ids: List[str],
        preferred_colours: List[str],
        excluded_colours: List[str],
        styles: List[str],
    ) -> "WardrobeFitCriteria":
        return WardrobeFitCriteria(
            compatible_ids=frozenset(compatible_ids),
            preferred_colours=frozenset(preferred_colours),
            excluded_colours=frozenset(excluded_colours),
            styles=frozenset(styles),
            enforce=bool(compatible_ids or preferred_colours or styles),
        )

    def score(self, w: WardrobeSummaryItem) -> Optional[int]:
        colours = {c for c in ((w.colour or "").lower(), (w.secondary_colour or "").lower()) if c}
        if colours & self.excluded_colours:
            return None
        s = 0
        if w.wardrobe_id in self.compatible_ids:
            s += 2
        if colours & self.preferred_colours:
            s += 1
        if (w.style or "").lower().replace(" ", "_") in self.styles:
            s += 1
        if self.enforce and s == 0:
            return None
        return s


def _norm_style(s: str) -> str:
    return s.lower().strip().replace(" ", "_")

class BuyNothingService:
    """
    Evaluates how existing wardrobe items can be styled or repurposed to
    complete an outfit without any new commercial purchase.
    """

    SUBSTITUTION_MAP: Dict[str, List[str]] = {
        "footwear": ["footwear", "shoes", "sneakers", "loafers", "heels", "flats", "sandals"],
        "shoes": ["footwear", "shoes", "sneakers", "loafers", "heels", "flats", "sandals"],
        "bag": ["bag", "handbag", "tote", "backpack", "clutch"],
        "accessory": ["accessory", "jewelry", "belt", "scarf", "hat"],
        "jewelry": ["jewelry", "accessory", "earrings", "necklace", "bracelet"],
        "outerwear": ["outerwear", "jacket", "blazer", "cardigan", "coat", "shirt", "blouse"],
        "top": ["top", "shirt", "blouse", "t-shirt"],
        "bottom": ["bottom", "pants", "jeans", "trousers", "skirt"],
    }

    def select_replacements(
        self,
        categories: List[str],
        available_wardrobe: List[WardrobeSummaryItem],
        taken_ids: Optional[Set[str]] = None,
        criteria: Optional[WardrobeFitCriteria] = None,
    ) -> List[Tuple[str, WardrobeSummaryItem]]:
        """Pick at most one owned item per category: highest compatibility
        signal first (Agent 1 list > requested colour/style), exact category
        before substitute type. With criteria.enforce, items that only match
        the category are never picked."""
        criteria = criteria or WardrobeFitCriteria()
        taken: Set[str] = set(taken_ids or set())
        picked: List[Tuple[str, WardrobeSummaryItem]] = []
        for cat in categories:
            norm = cat.lower().strip()
            substitutes = self.SUBSTITUTION_MAP.get(norm, [norm])
            candidates: List[Tuple[int, int, int, WardrobeSummaryItem]] = []
            for pos, w in enumerate(available_wardrobe):
                if w.wardrobe_id in taken:
                    continue
                w_cat = w.category.lower().strip()
                w_type = (w.type or "").lower().strip()
                if w_cat == norm or w_type == norm:
                    tier = 0
                elif w_cat in substitutes or w_type in substitutes:
                    tier = 1
                else:
                    continue
                score = criteria.score(w)
                if score is None:
                    continue
                candidates.append((-score, tier, pos, w))
            if candidates:
                candidates.sort()
                match = candidates[0][3]
                taken.add(match.wardrobe_id)
                picked.append((norm, match))
        return picked

    def assemble_buy_nothing_option(
        self,
        budget_ceiling: float,
        missing_categories: List[str],
        available_wardrobe: List[WardrobeSummaryItem],
        style_categories: Optional[List[str]] = None,
        criteria: Optional[WardrobeFitCriteria] = None,
    ) -> Optional[OutfitOption]:
        """Zero-purchase outfit option if wardrobe covers/substitutes the needs.

        Shows only the items that fill a needed category — never the whole
        wardrobe. When nothing is 'missing', style_categories (the required
        outfit categories from Agent 1) drive the selection."""
        targets = [c.lower().strip() for c in missing_categories] or [
            c.lower().strip() for c in (style_categories or [])
        ]
        if not available_wardrobe or not targets:
            return None

        picked = self.select_replacements(targets, available_wardrobe, criteria=criteria)
        if not picked:
            return None

        repurposed_items = [
            WardrobeRepurposedItem(
                wardrobe_id=w.wardrobe_id,
                category=w.category,
                type=w.type,
                colour=w.colour,
                repurpose_role=(
                    f"Repurposed owned {w.colour} {w.type} in place of purchasing {cat}"
                    if missing_categories
                    else f"Owned {w.colour} {w.type} styled for the {cat} piece"
                ),
                cost=0.0,
            )
            for cat, w in picked
        ]
        covered_categories = {cat for cat, _ in picked}

        coverage_ratio = len(covered_categories) / len(targets)
        relevance_score = round(0.70 + (0.25 * coverage_ratio), 2)

        cost_breakdown = CostBreakdown(
            total_cost=0.0,
            budget_ceiling=budget_ceiling,
            budget_remaining=budget_ceiling,
            savings_amount=budget_ceiling,
            savings_percentage=100.0,
            cost_per_category={cat: 0.0 for cat in (missing_categories or targets)},
        )

        item_names = [f"{r.colour} {r.type}" for r in repurposed_items]
        desc = (
            "100% sustainable combination utilizing your existing wardrobe: "
            f"{', '.join(item_names)}. Zero additional purchase cost."
        )

        explanation = (
            "Buy Nothing Mode: the outfit requirement can be fulfilled without spending any "
            f"money by restyling your existing {len(repurposed_items)} wardrobe item(s) "
            f"({', '.join(item_names)}). "
            f"This preserves 100% of your USD {budget_ceiling:,.2f} budget."
        )

        return OutfitOption(
            combination_id="OPT-BUY-NOTHING",
            strategy=OptimizationStrategy.BUY_NOTHING,
            name="Sustainable 'Buy Nothing' Mode",
            description=desc,
            selected_products=[],
            wardrobe_items_used=repurposed_items,
            cost_breakdown=cost_breakdown,
            budget_efficiency_score=1.0,
            relevance_score=relevance_score,
            overall_value_score=round((0.5 * relevance_score) + 0.5, 2),
            is_within_budget=True,
            financial_explanation=explanation,
        )


_buy_nothing_service = BuyNothingService()


def get_buy_nothing_service() -> BuyNothingService:
    return _buy_nothing_service
