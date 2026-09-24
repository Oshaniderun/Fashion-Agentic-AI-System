"""
Agent 2 — Fashion Information Retrieval
Shared Pydantic contracts between Agent 2 and the rest of FASHORA.

This file is the single source of truth for Agent 2's request/response shape
(Stage 1, defined 2026-09). Any change here must also be reflected in
docs/api/api-contracts.md and agreed with the team, since the Orchestrator,
Agent 3, and Agent 4 all build against this.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

from shared.constants import ProductCategory


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RetrievalStatus(str, Enum):
    """Set by Agent 2's own decision logic — see the relaxation ladder in
    agents/agent2_retrieval/app/decision_logic.py."""

    OK = "ok"                          # good matches found within all constraints
    RELAXED = "relaxed"                # matches found only after relaxing 1+ constraints
    LOW_CONFIDENCE = "low_confidence"  # best-effort results, constraints substantially loosened
    NO_RESULTS = "no_results"          # nothing found even after the full relaxation ladder


# ---------------------------------------------------------------------------
# Request: Orchestrator / Agent 3 -> Agent 2
# ---------------------------------------------------------------------------

class RetrievalRequest(BaseModel):
    request_id: str = Field(
        ...,
        description="Correlation ID set by the Orchestrator; carried through "
        "the whole pipeline for logging and the individual security assessment.",
    )
    required_category: ProductCategory
    preferred_colour: Optional[str] = Field(
        None, description="e.g. 'beige'. Optional — not every requirement specifies colour."
    )
    style: Optional[str] = Field(
        None,
        description="e.g. 'smart casual', 'elegant'. Free text for now — revisit "
        "as an enum once Agent 1 finalizes its style taxonomy.",
    )
    occasion: Optional[str] = Field(
        None, description="e.g. 'engagement', 'university event'. Passed through from Agent 1, not validated here."
    )
    query_text: Optional[str] = Field(
        None,
        description="Free-text search query, e.g. Agent 1's expanded query "
        "'beige women's loafers smart casual under LKR 5000'. Drives the BM25/semantic side of retrieval.",
    )
    max_price: float = Field(..., gt=0, description="Ceiling in LKR for this single item.")
    top_k: int = Field(5, ge=1, le=20, description="How many ranked results to return.")

    # --- feedback-loop fields (Agent 4 -> Agent 3 -> Agent 2) ---
    is_retry: bool = Field(
        False,
        description="True when this request was triggered by Agent 4 rejecting a "
        "previous candidate and Agent 3 asking for cheaper/different alternatives.",
    )
    retry_count: int = Field(
        0, ge=0, le=3, description="Retries so far this session. Orchestrator enforces the hard cap of 3."
    )
    excluded_product_ids: List[str] = Field(
        default_factory=list,
        description="Products already rejected in a previous round for this session — must not be returned again.",
    )


# ---------------------------------------------------------------------------
# Response: Agent 2 -> Orchestrator / Agent 3
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    """Sub-scores backing the weighted relevance formula from the proposal
    (0.30 semantic + 0.25 colour + 0.20 style + 0.15 budget + 0.10 availability).
    Kept separate so Agent 4 can explain *why*, not just show a number."""

    semantic_similarity: float = Field(..., ge=0, le=1)
    colour_match: float = Field(..., ge=0, le=1)
    style_match: float = Field(..., ge=0, le=1)
    budget_suitability: float = Field(..., ge=0, le=1)
    availability: float = Field(..., ge=0, le=1)


class ProductResult(BaseModel):
    product_id: str
    name: str
    category: ProductCategory
    colour: Optional[str] = "Unknown"
    price: Optional[float] = None
    store: str
    url: Optional[HttpUrl] = None
    availability: bool
    relevance_score: float = Field(..., ge=0, le=1, description="Weighted overall score — see score_breakdown.")
    score_breakdown: ScoreBreakdown

    # Security note (ties to the IR & Security individual assessment):
    # `name` and any future `description` field are external, unauthenticated
    # DATA. They are displayed to the user and to Agent 4, never concatenated
    # into an LLM prompt as an instruction. See
    # docs/architecture/agent2_decision_logic.md for the full rule.


class RetrievalResponse(BaseModel):
    request_id: str = Field(..., description="Echoes the request's ID so the Orchestrator can correlate.")
    status: RetrievalStatus
    results: List[ProductResult]
    relaxed_constraints: List[str] = Field(
        default_factory=list,
        description="Which constraints (if any) were loosened, e.g. ['colour', 'price_ceiling+15%']. "
        "Empty when status == OK.",
    )
    notes: Optional[str] = Field(
        None,
        description="Short human-readable note for Agent 4's explanation step, e.g. "
        "'No exact beige match; showing closest neutral tones.'",
    )
