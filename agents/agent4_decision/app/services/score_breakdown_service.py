"""
Feature 1 — per-candidate score breakdown.

Re-projects the signals the decision engine already computes onto the five
reported axes, weighted by configurable SB_W_* settings. This is an
EXPLANATION layer: ranking still uses the pre-existing `metrics.decision_score`
(W_* weights), which is reported alongside so nothing is silently re-based.

Scoring never reads gender, body type, skin tone or brand prestige — only
occasion/style/colour vocabulary, prices, availability and category coverage.
"""

from typing import Dict, List, Optional

from app.core.config import get_settings
from app.schemas.agent4_extensions import ScoreBreakdown, SubScores
from app.services.decision_service import EvaluatedOption, _norm
from shared.schemas.agent4_schemas import DecisionRequest, PieceSource, ValidationIssue

settings = get_settings()

# Style / occasion vocabulary -> the formality level it asks for (0 casual .. 1 formal).
_STYLE_FORMALITY = {
    "formal": 0.90,
    "semi_formal": 0.72,
    "business": 0.80,
    "business_casual": 0.55,
    "cocktail": 0.82,
    "elegant": 0.75,
    "smart_casual": 0.55,
    "party": 0.65,
    "traditional": 0.60,
    "casual": 0.30,
    "streetwear": 0.20,
    "sporty": 0.15,
}
_OCCASION_FORMALITY = {
    "interview": 0.85,
    "wedding": 0.85,
    "engagement": 0.80,
    "graduation": 0.65,
    "office": 0.75,
    "work": 0.70,
    "party": 0.65,
    "dinner": 0.60,
    "date": 0.50,
    "university": 0.35,
    "casual_outing": 0.30,
    "everyday": 0.25,
}
_NEUTRAL_FORMALITY = 0.50

# Agent 1's outfit-level colour judgement, used only as a small prior.
_COMPAT_COLOUR = {"excellent": 1.0, "good": 0.8, "moderate": 0.55, "clashing": 0.2}


def target_formality(request: DecisionRequest) -> float:
    """Formality the user asked for, from style first then occasion vocabulary."""
    ur = request.agent1_output.user_requirements
    for style in ur.style or []:
        level = _STYLE_FORMALITY.get(_norm(style))
        if level is not None:
            return level
    level = _OCCASION_FORMALITY.get(_norm(ur.occasion))
    return level if level is not None else _NEUTRAL_FORMALITY


def _colour_harmony(request: DecisionRequest, candidate: EvaluatedOption) -> float:
    fit = candidate.metrics.colour_fit
    compat = request.agent1_output.compatibility
    bucket = _COMPAT_COLOUR.get(_norm(getattr(compat, "colour_compatibility", None)))
    if bucket is None:
        return round(fit, 3)
    return round(0.75 * fit + 0.25 * bucket, 3)


def _formality_match(request: DecisionRequest, candidate: EvaluatedOption) -> float:
    """Distance between the asked-for formality and the outfit's own level.

    Owned items carry a detected `formality`; purchased items have no
    formality field upstream, so the candidate's style fit is the proxy.
    """
    wardrobe_formality = {
        w.wardrobe_id: w.formality for w in request.agent1_output.wardrobe
    }
    levels: List[float] = []
    for piece in candidate.pieces:
        if piece.source == PieceSource.WARDROBE and piece.item_id in wardrobe_formality:
            levels.append(wardrobe_formality[piece.item_id])
        else:
            levels.append(candidate.metrics.style_fit)
    actual = sum(levels) / len(levels) if levels else _NEUTRAL_FORMALITY
    return round(max(0.0, 1.0 - abs(actual - target_formality(request))), 3)


def _budget_fit(candidate: EvaluatedOption) -> float:
    """0.5 is the 'spends the whole budget but stays inside it' midpoint;
    going over budget decays with how far over."""
    efficiency = candidate.option.budget_efficiency_score
    if candidate.option.is_within_budget:
        return round(0.5 + 0.5 * efficiency, 3)
    cb = candidate.option.cost_breakdown
    overspend_ratio = (cb.budget_ceiling / cb.total_cost) if cb.total_cost > 0 else 0.0
    return round(max(0.0, 0.5 * efficiency * overspend_ratio), 3)


def _constraint_satisfaction(
    request: DecisionRequest,
    candidate: EvaluatedOption,
    issues: List[ValidationIssue],
) -> float:
    """Mean of the constraint terms that actually apply to this candidate."""
    terms: List[float] = [1.0 if candidate.passed else 0.0]

    required = [_norm(c) for c in request.agent1_output.outfit_requirements.required_categories if c]
    if required:
        covered = len(required) - len(candidate.unresolved)
        terms.append(max(0.0, min(1.0, covered / len(required))))

    if candidate.type_mismatches:
        terms.append(max(0.0, 1.0 - len(candidate.type_mismatches) / max(len(required), 1)))

    purchased = [p for p in candidate.pieces if p.source == PieceSource.PURCHASE]
    if purchased:
        terms.append(max(0.0, 1.0 - len(candidate.trust_warnings) / len(purchased)))

    if issues:
        flagged = {i.product_id for i in issues if i.severity.value == "error" and i.product_id}
        bad = sum(1 for p in purchased if p.item_id in flagged)
        terms.append(max(0.0, 1.0 - bad / max(len(purchased), 1)))

    return round(sum(terms) / len(terms), 3)


def build_breakdown(
    request: DecisionRequest,
    ranked: List[EvaluatedOption],
    issues: Optional[List[ValidationIssue]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[ScoreBreakdown]:
    """Sub-scores + weights + weighted total for the chosen outfit and runner-ups."""
    issues = issues or []
    weights = weights or settings.score_weights()
    breakdowns: List[ScoreBreakdown] = []

    for rank, candidate in enumerate(ranked[: settings.MAX_BREAKDOWN_CANDIDATES], start=1):
        sub = SubScores(
            colour_harmony=_colour_harmony(request, candidate),
            formality_match=_formality_match(request, candidate),
            occasion_fit=candidate.metrics.occasion_fit,
            budget_fit=_budget_fit(candidate),
            constraint_satisfaction=_constraint_satisfaction(request, candidate, issues),
        )
        overall = sum(weights[name] * value for name, value in sub.model_dump().items())
        breakdowns.append(
            ScoreBreakdown(
                combination_id=candidate.option.combination_id,
                rank=rank,
                selected=rank == 1,
                sub_scores=sub,
                weights=dict(weights),
                weights_version=settings.SCORE_WEIGHTS_VERSION,
                overall_score=round(min(max(overall, 0.0), 1.0), 4),
                decision_score=candidate.metrics.decision_score,
            )
        )
    return breakdowns
