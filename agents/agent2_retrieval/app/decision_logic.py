"""
Agent 2's decision logic — its one genuine decision point (required by the
project brief so each agent is more than a fixed pipeline stage).

Status: Stage 1 (defined 2026-09). This is control-flow / pseudocode with the
real retrieval calls stubbed out — fill in the TODOs during Stage 3
(implementation) once the BM25 + Sentence-Transformers engine exists.

--------------------------------------------------------------------------
DECISION: what to do when retrieval returns too few usable matches
--------------------------------------------------------------------------
Ladder — apply one relaxation at a time, re-run, stop as soon as
MIN_ACCEPTABLE_RESULTS is reached:

  1. Full-constraint retrieval (category + colour + style + price, as given).
  2. Relax colour: drop it as a hard filter, keep it as a soft semantic signal.
  3. Relax style: drop it as a hard filter, keep it as a soft semantic signal.
  4. Widen max_price by PRICE_RELAX_STEP (one step, not iterative). This only
     widens the *search* window — it does not override Agent 3's authority
     over the real budget; Agent 3/4 still decide whether to accept anything
     above the user's original ceiling.
  5. Return best-effort results, flagged LOW_CONFIDENCE (or NO_RESULTS if
     still empty).

required_category is NEVER relaxed — returning the wrong category of product
(a bag when shoes were asked for) is not an acceptable substitution and must
not happen silently.

--------------------------------------------------------------------------
DECISION: how to treat retrieved product content
--------------------------------------------------------------------------
Product `name` / `description` text comes from the product dataset — external,
unauthenticated data. It is DATA to display, never INSTRUCTIONS to follow.
Concretely:
  - Never concatenate product text into an LLM prompt as free-form instruction
    text; wrap it in a clearly labeled data field if it must be passed to an
    LLM at all (e.g. for the optional description-summarization feature).
  - A product record whose text looks like an injected instruction (e.g.
    "ignore previous instructions", "system:", embedded role markers) gets
    flagged, not silently cleaned and passed through. This is the intended
    attack surface for the IR & Security individual assessment — don't
    quietly defeat it here.
"""

from __future__ import annotations

from typing import List

from shared.schemas.agent2_schemas import (
    ProductResult,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalStatus,
)

MIN_ACCEPTABLE_RESULTS = 3
PRICE_RELAX_STEP = 0.15  # widen price ceiling by 15% on the final relaxation step


def resolve_retrieval(request: RetrievalRequest) -> RetrievalResponse:
    """Entry point: run the relaxation ladder and return a fully-formed
    RetrievalResponse. This is the function the FastAPI /retrieve-products
    route should call in Stage 3."""

    relaxed: List[str] = []

    # Step 1 — full constraints
    results = _run_retrieval(request, relax_colour=False, relax_style=False, price_ceiling=request.max_price)
    if len(results) >= MIN_ACCEPTABLE_RESULTS:
        return _build_response(request, results, RetrievalStatus.OK, relaxed)

    # Step 2 — relax colour
    relaxed.append("colour")
    results = _run_retrieval(request, relax_colour=True, relax_style=False, price_ceiling=request.max_price)
    if len(results) >= MIN_ACCEPTABLE_RESULTS:
        return _build_response(request, results, RetrievalStatus.RELAXED, relaxed)

    # Step 3 — also relax style
    relaxed.append("style")
    results = _run_retrieval(request, relax_colour=True, relax_style=True, price_ceiling=request.max_price)
    if len(results) >= MIN_ACCEPTABLE_RESULTS:
        return _build_response(request, results, RetrievalStatus.RELAXED, relaxed)

    # Step 4 — widen price ceiling (single step)
    widened_price = request.max_price * (1 + PRICE_RELAX_STEP)
    relaxed.append(f"price_ceiling+{int(PRICE_RELAX_STEP * 100)}%")
    results = _run_retrieval(request, relax_colour=True, relax_style=True, price_ceiling=widened_price)

    # Step 5 — best effort
    status = RetrievalStatus.LOW_CONFIDENCE if results else RetrievalStatus.NO_RESULTS
    return _build_response(request, results, status, relaxed)


def _run_retrieval(
    request: RetrievalRequest,
    *,
    relax_colour: bool,
    relax_style: bool,
    price_ceiling: float,
) -> List[ProductResult]:
    """
    TODO (Stage 3): replace with the real hybrid BM25 + Sentence-Transformers
    retrieval over the product dataset (agents/agent2_retrieval/data/), always
    hard-filtered by request.required_category and price_ceiling, with colour
    and style used as hard filters unless the corresponding relax_* flag is set
    (in which case fold them into the semantic ranking instead of filtering).
    Must also exclude request.excluded_product_ids.
    """
    raise NotImplementedError("Wire up the retrieval engine here in Stage 3")


def _build_response(
    request: RetrievalRequest,
    results: List[ProductResult],
    status: RetrievalStatus,
    relaxed: List[str],
) -> RetrievalResponse:
    """TODO (Stage 3): _run_retrieval should already attach a ScoreBreakdown
    per result; this just assembles the envelope and a human-readable note."""

    note = None
    if status == RetrievalStatus.LOW_CONFIDENCE:
        note = f"Best-effort results after relaxing: {', '.join(relaxed)}."
    elif status == RetrievalStatus.NO_RESULTS:
        note = f"No matches even after relaxing: {', '.join(relaxed)}."

    return RetrievalResponse(
        request_id=request.request_id,
        status=status,
        results=results,
        relaxed_constraints=relaxed,
        notes=note,
    )
