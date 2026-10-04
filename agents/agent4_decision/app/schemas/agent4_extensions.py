"""Local Pydantic models for Agent 4's additive response/request fields.

`shared/schemas/agent4_schemas.py` is the team-owned contract and is not
edited here, so every new field lives on a subclass that Agent 4 uses for its
own request parsing and response serialisation. Existing fields keep their
names, types and meaning; new fields are optional with safe defaults, so any
caller that ignores them is unaffected.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from shared.schemas.agent4_schemas import (
    DecisionRequest,
    DecisionResponse,
)

Scalar = Optional[Union[str, int, float]]


# ---------------------------------------------------------------------------
# Feature 1 — score breakdown
# ---------------------------------------------------------------------------

class SubScores(BaseModel):
    """The five reported decision axes, each normalised to 0..1."""

    colour_harmony: float = Field(..., ge=0.0, le=1.0)
    formality_match: float = Field(..., ge=0.0, le=1.0)
    occasion_fit: float = Field(..., ge=0.0, le=1.0)
    budget_fit: float = Field(..., ge=0.0, le=1.0)
    constraint_satisfaction: float = Field(..., ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    """One ranked candidate explained through the configurable sub-scores."""

    combination_id: str
    rank: int = Field(..., ge=1, description="1 = the chosen outfit.")
    selected: bool = False
    sub_scores: SubScores
    weights: Dict[str, float] = Field(
        ..., description="Weights actually used, keyed by sub-score name (sums to 1)."
    )
    weights_version: str
    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Weighted sum of the five sub-scores."
    )
    decision_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The pre-existing composite that still drives ranking "
        "(metrics.decision_score) — reported side by side so nothing is silently re-based.",
    )


# ---------------------------------------------------------------------------
# Feature 2 — structured rejection
# ---------------------------------------------------------------------------

class RejectReasonCode(str, Enum):
    STYLE_CLASH = "STYLE_CLASH"
    MISSING_REQUIRED_CATEGORY = "MISSING_REQUIRED_CATEGORY"
    OVER_BUDGET = "OVER_BUDGET"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INCOMPLETE_OUTFIT = "INCOMPLETE_OUTFIT"


class SuggestedAction(str, Enum):
    """The fixed vocabulary Agent 4 offers the orchestrator after a rejection."""

    RETRY_WITH_EXCLUSIONS = "retry_with_exclusions"
    INCREASE_BUDGET = "increase_budget"
    RELAX_CONSTRAINTS = "relax_constraints"
    ACCEPT_BEST_AVAILABLE = "accept_best_available"
    REQUEST_CLARIFICATION = "request_clarification"


class CandidateRejection(BaseModel):
    """Why one specific candidate was not chosen."""

    combination_id: str
    name: str
    reason_codes: List[RejectReasonCode] = Field(default_factory=list)
    detail: Optional[str] = Field(
        None, description="Human-readable form of the dominant reason."
    )
    product_ids: List[str] = Field(
        default_factory=list, description="Purchased products inside this candidate."
    )


# ---------------------------------------------------------------------------
# Feature 4 — counterfactuals
# ---------------------------------------------------------------------------

class CounterfactualKind(str, Enum):
    BUDGET_INCREASE = "budget_increase"
    NO_BUDGET_CHANGE = "no_budget_change"
    ITEM_SWAP = "item_swap"
    SUB_SCORE_FLIP = "sub_score_flip"


class Counterfactual(BaseModel):
    kind: CounterfactualKind
    field: str = Field(..., description="Machine-readable name of the changed input.")
    old_value: Scalar = None
    new_value: Scalar = None
    resulting_winner: Optional[str] = Field(
        None, description="combination_id that would win under new_value."
    )
    sub_score: Optional[str] = Field(
        None, description="Which sub-score explains the flip, when known."
    )
    sentence: str = Field(..., description="Human-readable counterfactual.")


# ---------------------------------------------------------------------------
# Feature 5 — audit log views
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    """One recorded decision. No request content, no user text, no PII."""

    decision_id: str
    recorded_at: str
    request_id: Optional[str] = None
    input_sha256: str
    candidate_ids: List[str] = Field(default_factory=list)
    score_breakdowns: List[Dict[str, Any]] = Field(default_factory=list)
    weights_version: str
    chosen_combination_id: Optional[str] = None
    decision_status: str
    reject_reason_codes: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    confidence_level: Optional[str] = None
    explanation_source: Optional[str] = None
    explanation_verified: Optional[bool] = None
    reoptimization_round: int = 0


class AuditPage(BaseModel):
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    items: List[AuditEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Extended request / response
# ---------------------------------------------------------------------------

class DecisionRequestExtended(DecisionRequest):
    """Adds the optional re-optimization round counter.

    Omitting it keeps today's behaviour exactly (round 0 = first attempt).
    """

    reoptimization_round: int = Field(
        0,
        ge=0,
        le=20,
        description="How many times this session has already been re-optimised. "
        "At MAX_REOPTIMIZATION_ROUNDS Agent 4 stops rejecting and returns its "
        "best available answer flagged retry_limit_reached.",
    )


class DecisionResponseExtended(DecisionResponse):
    """DecisionResponse plus every additive, optional Agent 4 extension."""

    # Feature 1
    score_breakdown: List[ScoreBreakdown] = Field(
        default_factory=list,
        description="Ranked sub-scores for the chosen outfit and runner-ups. "
        "Empty when no candidate could be evaluated.",
    )
    # Feature 2
    reason_codes: List[RejectReasonCode] = Field(
        default_factory=list, description="Populated only when nothing was acceptable."
    )
    candidate_rejections: List[CandidateRejection] = Field(default_factory=list)
    excluded_product_ids: List[str] = Field(
        default_factory=list,
        description="Products from rejected candidates; feed straight back into "
        "Agent 2/Agent 3's existing excluded_product_ids field.",
    )
    suggested_action: Optional[SuggestedAction] = Field(
        None, description="Deterministic next step, from a fixed vocabulary."
    )
    reoptimization_round: int = 0
    retry_limit_reached: bool = False
    retry_limit_reason: Optional[str] = None
    # Feature 3
    explanation_source: Optional[str] = Field(
        None, description="'template' or 'llm' — which text is in `explanation`."
    )
    explanation_verified: Optional[bool] = None
    verification_issues: List[str] = Field(default_factory=list)
    # Feature 4
    counterfactuals: List[Counterfactual] = Field(default_factory=list)
    # Feature 5
    decision_id: Optional[str] = Field(
        None, description="Audit-log key for this call; GET /audit/{decision_id}."
    )
