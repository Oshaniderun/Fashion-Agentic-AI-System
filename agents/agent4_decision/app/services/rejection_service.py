"""
Feature 2 — structured rejection.

Turns Agent 4's existing, unchanged hard-constraint decisions into
machine-readable reason codes so the orchestrator can feed rejected products
straight back into Agent 2 / Agent 3's existing ``excluded_product_ids`` field.

Deterministic: no LLM, no new rejection. A candidate is reported as rejected
here only when ``DecisionService`` already rejected it (or when nothing that
survived the hard constraints can complete the outfit).
"""

from typing import List, Optional

from app.core.config import get_settings
from app.schemas.agent4_extensions import (
    CandidateRejection,
    RejectReasonCode,
    SuggestedAction,
)
from app.services.decision_service import EvaluatedOption
from shared.schemas.agent4_schemas import (
    DecisionResponse,
    DecisionStatus,
    PieceSource,
    ValidationIssue,
)

settings = get_settings()

_INCOMPLETE = {RejectReasonCode.INCOMPLETE_OUTFIT, RejectReasonCode.MISSING_REQUIRED_CATEGORY}


def _purchase_ids(e: EvaluatedOption) -> List[str]:
    return [p.item_id for p in e.pieces if p.source == PieceSource.PURCHASE]


def _incomplete_codes(e: EvaluatedOption) -> List[RejectReasonCode]:
    if not e.unresolved:
        return []
    return [RejectReasonCode.MISSING_REQUIRED_CATEGORY, RejectReasonCode.INCOMPLETE_OUTFIT]


def _clash_codes(e: EvaluatedOption) -> List[RejectReasonCode]:
    return [RejectReasonCode.STYLE_CLASH] if e.type_mismatches else []


def candidate_rejections(
    evaluated: List[EvaluatedOption], response: DecisionResponse
) -> List[CandidateRejection]:
    """One entry per candidate Agent 4 could not offer."""
    out: List[CandidateRejection] = []
    nothing_complete = response.decision.status != DecisionStatus.COMPLETE
    for e in evaluated:
        if e.option.combination_id == response.selected_combination_id:
            continue
        if not e.passed:
            codes = [RejectReasonCode(c) for c in e.rejection_codes] or [
                RejectReasonCode.CONSTRAINT_VIOLATION
            ]
            codes += [c for c in _incomplete_codes(e) + _clash_codes(e) if c not in codes]
            out.append(
                CandidateRejection(
                    combination_id=e.option.combination_id,
                    name=e.option.name,
                    reason_codes=codes,
                    detail=e.rejection or "Did not satisfy the hard constraints.",
                    product_ids=_purchase_ids(e),
                )
            )
        elif nothing_complete and e.unresolved:
            out.append(
                CandidateRejection(
                    combination_id=e.option.combination_id,
                    name=e.option.name,
                    reason_codes=_incomplete_codes(e),
                    detail="Does not cover: " + ", ".join(e.unresolved),
                    product_ids=_purchase_ids(e),
                )
            )
    return out


def reason_codes(
    evaluated: List[EvaluatedOption],
    response: DecisionResponse,
    rejections: List[CandidateRejection],
) -> List[RejectReasonCode]:
    """Decision-level codes: why this call did not end in a complete outfit."""
    codes: List[RejectReasonCode] = []

    def add(code: RejectReasonCode) -> None:
        if code not in codes:
            codes.append(code)

    status = response.decision.status
    if status == DecisionStatus.NO_SUITABLE_OUTFIT or status == DecisionStatus.PARTIAL:
        for r in rejections:
            for c in r.reason_codes:
                add(c)
        if status == DecisionStatus.PARTIAL:
            # The winner itself left something uncovered — that is a rejection
            # of "this outfit is finished", so it must appear at decision level.
            chosen = next(
                (
                    e
                    for e in evaluated
                    if e.option.combination_id == response.selected_combination_id
                ),
                None,
            )
            if chosen is not None:
                for c in _incomplete_codes(chosen) + _clash_codes(chosen):
                    add(c)
        if response.decision.confidence_score < settings.LOW_CONFIDENCE_THRESHOLD:
            add(RejectReasonCode.LOW_CONFIDENCE)
    return codes


def excluded_product_ids(rejections: List[CandidateRejection]) -> List[str]:
    ids: List[str] = []
    for r in rejections:
        for pid in r.product_ids:
            if pid and pid not in ids:
                ids.append(pid)
    return ids[: settings.MAX_EXCLUDED_PRODUCT_IDS]


def suggested_action(
    codes: List[RejectReasonCode],
    *,
    at_retry_cap: bool,
    excluded_ids: List[str],
    status: DecisionStatus,
) -> Optional[SuggestedAction]:
    """The single next step the orchestrator should take, from a fixed vocabulary."""
    if status == DecisionStatus.INSUFFICIENT_INPUT:
        return SuggestedAction.REQUEST_CLARIFICATION
    if at_retry_cap:
        return SuggestedAction.ACCEPT_BEST_AVAILABLE
    if codes and set(codes) <= {RejectReasonCode.OVER_BUDGET, RejectReasonCode.LOW_CONFIDENCE}:
        return SuggestedAction.INCREASE_BUDGET
    if any(c in codes for c in _INCOMPLETE) or RejectReasonCode.CONSTRAINT_VIOLATION in codes:
        return (
            SuggestedAction.RETRY_WITH_EXCLUSIONS
            if excluded_ids
            else SuggestedAction.RELAX_CONSTRAINTS
        )
    if codes or excluded_ids:
        # Nothing blocks the answer, but these products failed verification or a
        # constraint — they should not resurface in the next round.
        return SuggestedAction.RETRY_WITH_EXCLUSIONS
    return None


def build(
    evaluated: List[EvaluatedOption],
    response: DecisionResponse,
    *,
    reoptimization_round: int = 0,
) -> dict:
    """All Feature 2 extension fields for one decision."""
    at_cap = reoptimization_round >= settings.MAX_REOPTIMIZATION_ROUNDS
    rejections = candidate_rejections(evaluated, response)
    codes = reason_codes(evaluated, response, rejections)
    excluded = excluded_product_ids(rejections)
    return {
        "candidate_rejections": rejections,
        "reason_codes": codes,
        "excluded_product_ids": excluded,
        "suggested_action": suggested_action(
            codes,
            at_retry_cap=at_cap,
            excluded_ids=excluded,
            status=response.decision.status,
        ),
        "retry_limit_reached": at_cap,
    }
