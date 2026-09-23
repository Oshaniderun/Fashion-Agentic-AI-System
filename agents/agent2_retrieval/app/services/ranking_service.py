"""
Ranking service computing multi-factor relevance scores and transparent ScoreBreakdown.
Formula aligned with FASHORA system proposal:
Relevance = 0.30 * semantic + 0.25 * colour + 0.20 * style + 0.15 * budget + 0.10 * availability
"""

from typing import Dict, Any, Optional
from shared.schemas.agent2_schemas import ScoreBreakdown

NEUTRAL_COLOUR_PAIRS = {
    ("beige", "cream"), ("cream", "beige"),
    ("beige", "khaki"), ("khaki", "beige"),
    ("blue", "navy blue"), ("navy blue", "blue"),
    ("navy", "navy blue"), ("navy blue", "navy"),
    ("black", "dark grey"), ("grey", "silver"),
    ("white", "cream"), ("gold", "rose gold")
}

class RankingService:
    @staticmethod
    def calculate_colour_match(requested_colour: Optional[str], product_colour: str) -> float:
        if not requested_colour:
            return 0.8  # No colour constraint specified, neutral positive

        req = requested_colour.strip().lower()
        prod = (product_colour or "").strip().lower()

        if req == prod or req in prod or prod in req:
            return 1.0

        if (req, prod) in NEUTRAL_COLOUR_PAIRS or (prod, req) in NEUTRAL_COLOUR_PAIRS:
            return 0.75

        return 0.2

    @staticmethod
    def calculate_style_match(requested_style: Optional[str], product_style: str) -> float:
        if not requested_style:
            return 0.8  # No style constraint specified

        req = requested_style.strip().lower()
        prod = (product_style or "").strip().lower()

        if req == prod or req in prod or prod in req:
            return 1.0

        # Compatible styles (e.g. smart casual matches casual or elegant)
        if ("casual" in req and "casual" in prod) or ("elegant" in req and "classic" in prod):
            return 0.75

        return 0.3

    @staticmethod
    def calculate_budget_suitability(price: float, max_price: float) -> float:
        if max_price <= 0:
            return 0.0
        if price <= max_price:
            # Within budget: high score, slightly favoring efficient cost within reason
            ratio = price / max_price
            return round(max(0.5, 1.0 - (0.2 * ratio)), 4)
        else:
            # Over budget (during relaxation): penalties proportional to excess
            excess_ratio = (price - max_price) / max_price
            return round(max(0.0, 1.0 - (2.0 * excess_ratio)), 4)

    @classmethod
    def compute_score(
        cls,
        bm25_score: float,
        dense_similarity: float,
        product_price: float,
        max_price: float,
        product_colour: str,
        requested_colour: Optional[str],
        product_style: str,
        requested_style: Optional[str],
        is_available: bool,
    ) -> tuple[float, ScoreBreakdown]:
        # Semantic similarity blends BM25 lexical + dense vector
        # If one is 0.0 or unavailable, blends gracefully
        if bm25_score > 0 and dense_similarity > 0:
            sem_sim = 0.5 * bm25_score + 0.5 * dense_similarity
        elif dense_similarity > 0:
            sem_sim = dense_similarity
        else:
            sem_sim = bm25_score
        sem_sim = round(max(0.0, min(1.0, sem_sim)), 4)

        col_match = round(cls.calculate_colour_match(requested_colour, product_colour), 4)
        sty_match = round(cls.calculate_style_match(requested_style, product_style), 4)
        bud_suit = round(cls.calculate_budget_suitability(product_price, max_price), 4)
        avail_score = 1.0 if is_available else 0.0

        # 0.30 semantic + 0.25 colour + 0.20 style + 0.15 budget + 0.10 availability
        weighted_score = (
            0.30 * sem_sim
            + 0.25 * col_match
            + 0.20 * sty_match
            + 0.15 * bud_suit
            + 0.10 * avail_score
        )
        weighted_score = round(max(0.0, min(1.0, weighted_score)), 4)

        breakdown = ScoreBreakdown(
            semantic_similarity=sem_sim,
            colour_match=col_match,
            style_match=sty_match,
            budget_suitability=bud_suit,
            availability=avail_score,
        )

        return weighted_score, breakdown
