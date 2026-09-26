"""
Payload factories for Agent 4 tests.

Builds genuine Agent 1 / Agent 2 / Agent 3 contract instances so the tests
exercise the real Pydantic validation path, exactly as the orchestrator
would supply them at runtime.
"""

from typing import List, Optional

from shared.schemas.agent1_schemas import (
    Agent1OutputContract,
    Agent2SearchRequirement,
    ConfidenceMetrics,
    OutfitRequirements,
    RequestedItem,
    UserRequirements,
    WardrobeSummaryItem,
)
from shared.schemas.agent2_schemas import (
    ProductResult,
    RetrievalResponse,
    RetrievalStatus,
    ScoreBreakdown,
)
from shared.schemas.agent3_schemas import (
    BudgetOptimizationResponse,
    BudgetSource,
    BudgetStatus,
    CandidateProductItem,
    CostBreakdown,
    OptimizationStrategy,
    OutfitOption,
    WardrobeRepurposedItem,
)
from shared.schemas.agent4_schemas import DecisionRequest

REQ_ID = "REQ-TEST-0001"


def wardrobe_item(
    wardrobe_id: str = "W001",
    category: str = "top",
    type_: str = "blouse",
    colour: str = "white",
    style: str = "smart_casual",
) -> WardrobeSummaryItem:
    return WardrobeSummaryItem(
        wardrobe_id=wardrobe_id, category=category, type=type_, colour=colour, style=style
    )


def agent1_output(
    required: List[str] = ("top",),
    missing: List[str] = (),
    excluded_colours: List[str] = (),
    styles: List[str] = ("smart_casual",),
    colour_prefs: List[str] = (),
    occasion: Optional[str] = "dinner",
    wardrobe: Optional[List[WardrobeSummaryItem]] = None,
    clarification: bool = False,
    suitability: str = "high",
    item_types: Optional[dict] = None,
) -> Agent1OutputContract:
    required = list(required)
    missing = list(missing)
    available = [c for c in required if c not in missing]
    item_types = item_types or {}
    return Agent1OutputContract(
        request_id=REQ_ID,
        user_requirements=UserRequirements(            occasion=occasion,
            style=list(styles),
            colour_preferences=list(colour_prefs),
            excluded_colours=list(excluded_colours),
            budget=200.0,
            requested_types=[t for t in item_types.values() if t],
            identified_items=[
                RequestedItem(category=c, colour="white", type=item_types.get(c))
                for c in required
            ],
        ),
        wardrobe=wardrobe if wardrobe is not None else [wardrobe_item()],
        outfit_requirements=OutfitRequirements(
            required_categories=required,
            available_categories=available,
            missing_categories=missing,
            clarification_needed=clarification,
            clarification_message="What did you mean?" if clarification else None,
        ),
        confidence=ConfidenceMetrics(overall=0.9, nlp=0.9),
        search_requirements=Agent2SearchRequirement(
            categories=missing, style=list(styles), occasion=occasion
        ),
        compatibility=_compat(suitability),
    )


def _compat(suitability: str):
    from shared.schemas.agent1_schemas import CompatibilityDetails

    return CompatibilityDetails(
        style="smart_casual",
        occasion_suitability=suitability,
        colour_compatibility="good",
        score=0.8,
        explanation="test",
    )


def product(
    product_id: str = "P1",
    category: str = "top",
    colour: str = "white",
    price: float = 40.0,
    name: Optional[str] = None,
    availability: bool = True,
    relevance: float = 0.9,
    style_match: float = 0.9,
    colour_match: float = 0.9,
) -> ProductResult:
    return ProductResult(
        product_id=product_id,
        name=name or f"{colour} {category} item",
        category=category,
        colour=colour,
        price=price,
        store="Test Retailer",
        availability=availability,
        relevance_score=relevance,
        score_breakdown=ScoreBreakdown(
            semantic_similarity=0.9,
            colour_match=colour_match,
            style_match=style_match,
            budget_suitability=0.9,
            availability=1.0 if availability else 0.0,
        ),
    )


def retrieval_response(products: List[ProductResult]) -> RetrievalResponse:
    return RetrievalResponse(
        request_id=REQ_ID,
        status=RetrievalStatus.OK if products else RetrievalStatus.NO_RESULTS,
        results=products,
    )


def candidate(p: ProductResult) -> CandidateProductItem:
    return CandidateProductItem(
        product_id=p.product_id,
        name=p.name,
        category=p.category.value if hasattr(p.category, "value") else str(p.category),
        colour=p.colour,
        price=p.price,
        store=p.store,
        relevance_score=p.relevance_score,
        availability=p.availability,
    )


def option(
    combination_id: str = "OPT-BEST-VALUE",
    strategy: OptimizationStrategy = OptimizationStrategy.BEST_VALUE,
    products: List[CandidateProductItem] = (),
    wardrobe_items: List[WardrobeRepurposedItem] = (),
    budget_ceiling: float = 200.0,
    efficiency: float = 0.7,
    within_budget: bool = True,
) -> OutfitOption:
    total = round(sum(p.price for p in products), 2)
    return OutfitOption(
        combination_id=combination_id,
        strategy=strategy,
        name=f"Option {combination_id}",
        description="test option",
        selected_products=list(products),
        wardrobe_items_used=list(wardrobe_items),
        cost_breakdown=CostBreakdown(
            total_cost=total,
            budget_ceiling=budget_ceiling,
            budget_remaining=round(budget_ceiling - total, 2),
            savings_amount=round(max(budget_ceiling - total, 0), 2),
            savings_percentage=round(max(budget_ceiling - total, 0) / budget_ceiling * 100, 1)
            if budget_ceiling
            else 0.0,
        ),
        budget_efficiency_score=efficiency,
        relevance_score=0.85,
        overall_value_score=0.8,
        is_within_budget=within_budget,
        financial_explanation="test",
    )


def repurposed(
    wardrobe_id: str = "W001",
    category: str = "top",
    type_: str = "blouse",
    colour: str = "white",
    role: str = "Direct match from wardrobe",
) -> WardrobeRepurposedItem:
    return WardrobeRepurposedItem(
        wardrobe_id=wardrobe_id, category=category, type=type_, colour=colour, repurpose_role=role
    )


def decision_request(
    options: List[OutfitOption],
    a1: Optional[Agent1OutputContract] = None,
    products_by_category: Optional[dict] = None,
    request_id: str = REQ_ID,
    user_id: Optional[str] = None,
    budget_status: BudgetStatus = BudgetStatus.WITHIN_BUDGET,
    budget_ceiling: float = 200.0,
) -> DecisionRequest:
    a1 = a1 or agent1_output()
    a3 = BudgetOptimizationResponse(
        request_id=request_id,
        status=budget_status,
        budget_ceiling=budget_ceiling,
        budget_source=BudgetSource.USER_STATED,
        options=list(options),
        recommended_option_id=options[0].combination_id if options else None,
    )
    retrieval = {
        cat: retrieval_response(items if isinstance(items, list) else [items])
        for cat, items in (products_by_category or {}).items()
    }
    return DecisionRequest(
        request_id=request_id,
        agent1_output=a1,
        budget_response=a3,
        retrieval_by_category=retrieval,
        user_id=user_id,
    )
