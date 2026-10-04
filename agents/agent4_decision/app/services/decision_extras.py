"""
Additive response decoration for Agent 4.

`DecisionService` keeps producing exactly the response it always did; this
module layers the optional extension fields on top of it in one place, so the
decision engine itself stays untouched and every new field is traceable to a
single call site.

The one behaviour this module can change is the retry cap: once
``reoptimization_round`` reaches ``MAX_REOPTIMIZATION_ROUNDS`` Agent 4 stops
rejecting and returns its best available candidate. That path only ever runs
on a call that would otherwise have answered "no suitable outfit", so today's
behaviour below the cap is byte-for-byte identical.
"""

from typing import List, Optional

from app.core.config import get_settings
from app.schemas.agent4_extensions import (
    DecisionResponseExtended,
    ScoreBreakdown,
    SuggestedAction,
)
from app.services import counterfactual_service, explanation_verifier, rejection_service
from app.services.decision_service import DecisionService, EvaluatedOption
from app.services.score_breakdown_service import build_breakdown
from shared.schemas.agent4_schemas import (
    ConfidenceLevel,
    DecisionOutcome,
    DecisionRequest,
    PieceSource,
    ValidationIssue,
)

settings = get_settings()


def _ranked_for_explanation(
    response, evaluated: List[EvaluatedOption]
) -> List[EvaluatedOption]:
    """Chosen candidate first, then runner-ups in the engine's own order."""
    selected_id = response.selected_combination_id
    if not selected_id:
        return []
    by_id = {e.option.combination_id: e for e in evaluated}
    ordered = [by_id[selected_id]] if selected_id in by_id else []
    for alt in response.alternatives:
        entry = by_id.get(alt.combination_id)
        if entry is not None and entry not in ordered:
            ordered.append(entry)
    return ordered


def score_breakdown_for(
    request: DecisionRequest,
    response,
    evaluated: List[EvaluatedOption],
    issues: Optional[List[ValidationIssue]] = None,
) -> List[ScoreBreakdown]:
    return build_breakdown(
        request,
        _ranked_for_explanation(response, evaluated),
        issues if issues is not None else response.validation_issues,
    )


def _is_buy_nothing(e: EvaluatedOption) -> bool:
    return all(p.source == PieceSource.WARDROBE for p in e.pieces)


def _forced_at_cap(
    service: DecisionService,
    request: DecisionRequest,
    response,
    evaluated: List[EvaluatedOption],
):
    """Best available candidate instead of another rejection, confidence forced Low.

    A zero-purchase (buy-nothing) candidate is preferred: after repeated failed
    rounds the cheapest safe answer is the one that spends nothing.
    """
    if response.selected_combination_id or not evaluated:
        return None
    ranked = sorted(evaluated, key=service._rank_key(request))
    best = next((e for e in ranked if _is_buy_nothing(e)), None) or ranked[0]
    ordered = [best] + [e for e in ranked if e is not best]
    forced = service._finalize(
        request,
        ordered,
        list(response.validation_issues),
        request.budget_response.budget_ceiling,
    )
    return forced.model_copy(
        update={
            "decision": DecisionOutcome(
                status=forced.decision.status,
                confidence_score=settings.FORCED_LOW_CONFIDENCE_SCORE,
                confidence_level=ConfidenceLevel.LOW,
            )
        }
    )


def _retry_limit_reason(codes: List, combination_id: Optional[str]) -> str:
    cap = settings.MAX_REOPTIMIZATION_ROUNDS
    if combination_id is None:
        return (
            f"The re-optimization limit of {cap} rounds was reached and the purchase "
            "planner still supplied no usable candidate, so nothing can be offered. "
            "A wider search or different requirements is needed."
        )
    if not codes:
        return (
            f"The re-optimization limit of {cap} rounds was reached, so no further "
            f"rejection is made. {combination_id} stands as the recommendation."
        )
    return (
        f"The re-optimization limit of {cap} rounds was reached, so the search was not "
        f"rejected again. {combination_id} is returned as the best available option even "
        "though it " + _imperfect_phrase(codes) + "."
    )


def _imperfect_phrase(codes: List) -> str:
    names = {
        "OVER_BUDGET": "goes over the stated budget",
        "MISSING_REQUIRED_CATEGORY": "leaves a required category uncovered",
        "INCOMPLETE_OUTFIT": "is not a complete outfit",
        "CONSTRAINT_VIOLATION": "breaks one of your stated constraints",
        "STYLE_CLASH": "does not match the requested style or garment type",
        "LOW_CONFIDENCE": "is a weak match",
    }
    parts = [names.get(getattr(c, "value", c), "is imperfect") for c in codes]
    return " and ".join(parts) if parts else "is imperfect"


def _explanation_fields(
    request: DecisionRequest,
    response,
    evaluated: List[EvaluatedOption],
    template_explanation: Optional[str],
):
    """Feature 3: label the narrative and verify it against the supplied data.

    An unverified Gemini rewrite is discarded in favour of the deterministic
    template; the template itself is verified too, and a failure is reported
    rather than hidden (there is nothing safer to fall back to).
    """
    chosen = next(
        (e for e in _ranked_for_explanation(response, evaluated)),
        None,
    )
    chosen_pieces = chosen.pieces if chosen is not None else ()
    all_pieces = [p for e in evaluated for p in e.pieces]

    text = response.explanation
    source = "template"
    if template_explanation is not None and text != template_explanation:
        polished = explanation_verifier.verify(
            text, request, chosen_pieces=chosen_pieces, all_pieces=all_pieces
        )
        if polished.verified:
            return "llm", True, [], text
        response = response.model_copy(update={"explanation": template_explanation})
        text = template_explanation

    result = explanation_verifier.verify(
        text, request, chosen_pieces=chosen_pieces, all_pieces=all_pieces
    )
    return source, result.verified, result.issues, text


def decorate(
    request: DecisionRequest,
    response,
    evaluated: List[EvaluatedOption],
    *,
    service: Optional[DecisionService] = None,
    reoptimization_round: int = 0,
    template_explanation: Optional[str] = None,
) -> DecisionResponseExtended:
    """Return the same response plus every optional extension field populated so far."""
    at_cap = reoptimization_round >= settings.MAX_REOPTIMIZATION_ROUNDS
    forced_answer = False
    extras = rejection_service.build(
        evaluated, response, reoptimization_round=reoptimization_round
    )

    if at_cap and service is not None:
        forced = _forced_at_cap(service, request, response, evaluated)
        if forced is not None:
            prior_codes = extras["reason_codes"]
            response = forced
            forced_answer = True
            template_explanation = forced.explanation  # freshly built, deterministic
            extras = rejection_service.build(
                evaluated, response, reoptimization_round=reoptimization_round
            )
            # Keep the codes that caused the earlier rejections: the caller must
            # still see why the forced answer is imperfect.
            extras["reason_codes"] = prior_codes
            extras["suggested_action"] = SuggestedAction.ACCEPT_BEST_AVAILABLE

    source, verified, issues, explanation_text = _explanation_fields(
        request, response, evaluated, template_explanation
    )
    if explanation_text != response.explanation:
        response = response.model_copy(update={"explanation": explanation_text})
    extras.update(
        {
            "explanation_source": source,
            "explanation_verified": verified,
            "verification_issues": issues,
        }
    )

    extras.update(
        {
            "score_breakdown": score_breakdown_for(request, response, evaluated),
            "reoptimization_round": reoptimization_round,
            "counterfactuals": counterfactual_service.build(
                request, response, evaluated, service=service, skip=forced_answer
            ),
            "retry_limit_reason": (
                _retry_limit_reason(
                    extras["reason_codes"], response.selected_combination_id
                )
                if at_cap
                else None
            ),
        }
    )

    payload = response.model_dump(mode="json")
    payload.update(extras)
    return DecisionResponseExtended(**payload)
