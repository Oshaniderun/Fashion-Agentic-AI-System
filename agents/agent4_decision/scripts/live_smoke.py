"""Live-server smoke: a realistic A1+A2+A3 payload -> A4 /decision/recommend.

Run against the already-up uvicorn on :8004 with the inter-agent service
token. Exercises the same Pydantic contracts the frontend/orchestrator posts,
so a pass proves the wiring (proxy-free) works over real HTTP.
"""
import os
os.environ.setdefault("LLM_PROVIDER", "mock")

import httpx

from app.core.config import get_settings
from shared.schemas.agent1_schemas import (
    Agent1OutputContract, Agent2SearchRequirement, ConfidenceMetrics,
    OutfitRequirements, RequestedItem, UserRequirements, WardrobeSummaryItem,
)
from shared.schemas.agent2_schemas import (
    ProductResult, RetrievalResponse, RetrievalStatus, ScoreBreakdown,
)
from shared.schemas.agent3_schemas import (
    BudgetOptimizationResponse, BudgetSource, BudgetStatus, CandidateProductItem,
    CostBreakdown, OptimizationStrategy, OutfitOption, WardrobeRepurposedItem,
)
from shared.schemas.agent4_schemas import DecisionRequest

RID = "REQ-LIVE-0001"

blouse = ProductResult(
    product_id="B08WHITE01", name="White checked cotton blouse", category="top",
    colour="white", price=38.0, store="Amazon", availability=True, relevance_score=0.91,
    score_breakdown=ScoreBreakdown(
        semantic_similarity=0.9, colour_match=0.95, style_match=0.85,
        budget_suitability=0.9, availability=1.0,
    ),
)

a1 = Agent1OutputContract(
    request_id=RID,
    user_requirements=UserRequirements(
        occasion="dinner", style=["smart_casual"], colour_preferences=[],
        excluded_colours=["neon"], budget=150.0,
        identified_items=[RequestedItem(category="top", type="blouse", colour="white", role="requested")],
    ),
    wardrobe=[
        WardrobeSummaryItem(wardrobe_id="W001", category="bottom", type="trouser",
                            colour="black", style="smart_casual", formality=0.6),
        WardrobeSummaryItem(wardrobe_id="W002", category="footwear", type="loafer",
                            colour="brown", style="smart_casual", formality=0.6),
    ],
    outfit_requirements=OutfitRequirements(
        required_categories=["top", "bottom", "footwear"],
        available_categories=["bottom", "footwear"], missing_categories=["top"],
    ),
    compatible_items=["W001", "W002"],
    confidence=ConfidenceMetrics(overall=0.88, nlp=0.9),
    search_requirements=Agent2SearchRequirement(categories=["top"], style=["smart_casual"],
                                                colour_preferences=["white"], occasion="dinner"),
)

def cand(p: ProductResult) -> CandidateProductItem:
    return CandidateProductItem(
        product_id=p.product_id, name=p.name, category=p.category.value,
        colour=p.colour, price=p.price, store=p.store,
        relevance_score=p.relevance_score, availability=p.availability,
    )

def cb(total):
    return CostBreakdown(total_cost=total, budget_ceiling=150.0,
                         budget_remaining=150.0 - total,
                         savings_amount=max(150.0 - total, 0.0),
                         savings_percentage=max(round((150.0 - total) / 150.0 * 100, 1), 0.0))

def wpi(wardrobe_id, cat, type_, colour, role):
    return WardrobeRepurposedItem(wardrobe_id=wardrobe_id, category=cat, type=type_,
                                  colour=colour, repurpose_role=role)

opts = [
    OutfitOption(
        combination_id="OPT-BEST-VALUE", strategy=OptimizationStrategy.BEST_VALUE,
        name="Best value outfit", description="Buy white blouse, reuse trousers and loafers.",
        selected_products=[cand(blouse)],
        wardrobe_items_used=[wpi("W001", "bottom", "trouser", "black", "Trousers"),
                             wpi("W002", "footwear", "loafer", "brown", "Shoes")],
        cost_breakdown=cb(38.0), budget_efficiency_score=0.82, relevance_score=0.9,
        overall_value_score=0.86, is_within_budget=True, financial_explanation="Within budget.",
    ),
    OutfitOption(
        combination_id="OPT-BAD-PRICE", strategy=OptimizationStrategy.TOP_MATCH,
        name="Top match (stale price)", description="Blouse priced wrong vs Agent 2.",
        selected_products=[cand(blouse).model_copy(update={"price": 999.0})],
        wardrobe_items_used=[wpi("W001", "bottom", "trouser", "black", "Trousers")],
        cost_breakdown=cb(999.0), budget_efficiency_score=0.1, relevance_score=0.9,
        overall_value_score=0.2, is_within_budget=False, financial_explanation="Over budget.",
    ),
]

a3 = BudgetOptimizationResponse(
    request_id=RID, status=BudgetStatus.WITHIN_BUDGET, budget_ceiling=150.0,
    budget_source=BudgetSource.USER_STATED, options=opts,
    recommended_option_id="OPT-BEST-VALUE",
)

req = DecisionRequest(
    request_id=RID, agent1_output=a1, budget_response=a3,
    retrieval_by_category={"top": RetrievalResponse(
        request_id=RID, status=RetrievalStatus.OK, results=[blouse])},
)

s = get_settings()
base = "http://127.0.0.1:8004"
hdrs = {"Authorization": f"Bearer {s.AGENT_SERVICE_TOKEN}"}

with httpx.Client(timeout=20) as c:
    r = c.post(f"{base}/decision/recommend", json=req.model_dump(mode="json"), headers=hdrs)
    print("recommend:", r.status_code)
    b = r.json()
    print("  status   :", b["decision"]["status"])
    print("  selected :", b["selected_combination_id"], "| strategy:", b["strategy"])
    print("  confidence:", b["decision"]["confidence_level"], b["decision"]["confidence_score"])
    print("  outfit   :", [(p["source"], p["category"], p["name"]) for p in b["outfit"]])
    print("  budget   :", b["budget"])
    print("  purchase :", b["purchase_summary"])
    print("  issues   :", [(i["code"], i.get("product_id")) for i in b["validation_issues"]])
    print("  explain  :", b["explanation"][:220])

    r2 = c.post(f"{base}/decision/analyze", json=req.model_dump(mode="json"), headers=hdrs)
    print("analyze:", r2.status_code,
          [(x["combination_id"], x["passed_hard_constraints"], x["rejection_reason"])
           for x in r2.json()["evaluated_candidates"]])
