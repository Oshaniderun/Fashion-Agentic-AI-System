"""
Agent 4 — Outfit Decision & Personalization
Shared Pydantic contracts between Agent 4 and the rest of FASHORA.

Agent 4 is the decision layer: it consumes the *validated* outputs of
Agent 1 (requirements + wardrobe), Agent 2 (retrieved products) and
Agent 3 (budget-feasible outfit options) and chooses the single best
complete outfit, with a confidence score and an explanation.

Design rules (mirroring the plan and Agents 1-3):
- Agent 4 never recomputes Agent 3's financials — it reuses them.
- Final products come only from validated Agent 2 / Agent 3 data (no invention).
- Currency is USD, consistent with the rest of the system.
- Product text is untrusted DATA, never an instruction.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

from shared.schemas.agent1_schemas import Agent1OutputContract
from shared.schemas.agent2_schemas import RetrievalResponse
from shared.schemas.agent3_schemas import BudgetOptimizationResponse


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DecisionStatus(str, Enum):
    """Outcome of Agent 4's decision."""
    COMPLETE = "complete"                       # a full, compatible, in-budget outfit was chosen
    PARTIAL = "partial"                         # outfit proposed but some required categories unresolved
    NO_SUITABLE_OUTFIT = "no_suitable_outfit"   # no candidate passed the hard constraints
    INSUFFICIENT_INPUT = "insufficient_input"    # upstream data missing/invalid; cannot decide


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PieceSource(str, Enum):
    WARDROBE = "wardrobe"    # an item the user already owns (0 cost)
    PURCHASE = "purchase"    # a new product to buy


class IssueSeverity(str, Enum):
    ERROR = "error"      # blocks trusting a value / candidate
    WARNING = "warning"  # noted, lowers confidence, does not hard-reject


# ---------------------------------------------------------------------------
# Input: caller (Orchestrator / frontend) supplies all three upstream payloads
# ---------------------------------------------------------------------------

class DecisionRequest(BaseModel):
    request_id: str = Field(..., description="Correlation ID shared across the pipeline.")
    agent1_output: Agent1OutputContract = Field(
        ..., description="Verbatim, already-validated Agent 1 output contract."
    )
    budget_response: BudgetOptimizationResponse = Field(
        ..., description="Verbatim Agent 3 budget-feasible options; its financials are reused, not recomputed."
    )
    retrieval_by_category: Dict[str, RetrievalResponse] = Field(
        default_factory=dict,
        description="Agent 2's per-category responses, used to cross-check that every "
        "purchased product genuinely exists and its price/availability match (hallucination guard)."
    )
    user_id: Optional[Union[str, int]] = Field(
        None, description="User ID for IDOR validation. Agent 4 stores nothing itself."
    )
    prefer_minimal_purchases: bool = Field(
        default=True,
        description="Tie-break toward reusing the wardrobe / buying less, per FASHORA's "
        "purchase-minimization goal."
    )


# ---------------------------------------------------------------------------
# Output sub-models
# ---------------------------------------------------------------------------

class OutfitPiece(BaseModel):
    """One element of the final outfit — owned or to-buy."""
    source: PieceSource
    item_id: str = Field(..., description="wardrobe_id (owned) or product_id (purchase).")
    category: str
    name: str
    colour: Optional[str] = None
    type: Optional[str] = None
    price_usd: Optional[float] = Field(None, description="Purchase price; None if not listed. Owned items are 0.")
    store: Optional[str] = None
    url: Optional[str] = None
    availability: Optional[bool] = None
    relevance_score: Optional[float] = Field(None, description="Agent 2 relevance for purchased items.")
    role: str = Field("completes requirement", description="Why this piece is in the outfit.")


class CandidateMetrics(BaseModel):
    """Transparent, structured scoring attributes — Agent 4 does not ask the LLM 'which is best'."""
    occasion_fit: float = Field(..., ge=0.0, le=1.0)
    style_fit: float = Field(...)
    colour_fit: float = Field(...)
    wardrobe_reuse: float = Field(..., description="Share of required categories filled by owned items.")
    retrieval_relevance: float = Field(..., description="Mean Agent 2 relevance across purchased items.")
    budget_efficiency: float = Field(..., description="Agent 3's budget_efficiency_score, reused.")
    purchase_count: int = Field(...)
    within_budget: bool = Field(...)
    is_complete: bool = Field(..., description="Every required category is covered.")
    decision_score: float = Field(..., ge=0.0, le=1.0, description="Composite weighted score.")


class EvaluatedCandidate(BaseModel):
    combination_id: str
    strategy: str
    name: str
    total_cost_usd: float
    metrics: CandidateMetrics
    passed_hard_constraints: bool
    rejection_reason: Optional[str] = None
    selected: bool = False


class BudgetOutcome(BaseModel):
    """Financials lifted directly from the selected Agent 3 option — never recomputed."""
    maximum_usd: float
    additional_cost_usd: float
    remaining_usd: float
    within_budget: bool


class PurchaseSummary(BaseModel):
    purchase_count: int
    existing_items_used: int


class AlternativeOutfit(BaseModel):
    combination_id: str
    strategy: str
    name: str
    total_cost_usd: float
    within_budget: bool
    decision_score: float
    reason: str


class ValidationIssue(BaseModel):
    severity: IssueSeverity
    code: str
    message: str
    product_id: Optional[str] = None
    field: Optional[str] = None


class DecisionOutcome(BaseModel):
    status: DecisionStatus
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class DecisionAnalysisResponse(BaseModel):
    """Diagnostic view: how every candidate was validated and scored."""
    request_id: str
    decision: DecisionOutcome
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    evaluated_candidates: List[EvaluatedCandidate] = Field(default_factory=list)
    unresolved_requirements: List[str] = Field(default_factory=list)
    currency: str = "USD"


class DecisionResponse(BaseModel):
    """The final, user-facing recommendation."""
    request_id: str
    decision: DecisionOutcome
    selected_combination_id: Optional[str] = None
    strategy: Optional[str] = None
    outfit: List[OutfitPiece] = Field(default_factory=list)
    budget: BudgetOutcome
    purchase_summary: PurchaseSummary
    metrics: Optional[CandidateMetrics] = None
    alternatives: List[AlternativeOutfit] = Field(default_factory=list)
    unresolved_requirements: List[str] = Field(default_factory=list)
    explanation: str
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    currency: str = "USD"


class AlternativesResponse(BaseModel):
    request_id: str
    alternatives: List[AlternativeOutfit] = Field(default_factory=list)
