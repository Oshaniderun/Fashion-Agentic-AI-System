"""
Agent 4's deterministic decision engine.

Pipeline (hard constraints always evaluated BEFORE any scoring, per the
system design):

  validate inputs -> build candidates from Agent 3 options
  -> hard constraints (verifiable products, availability, excluded colours,
     budget feasibility, completeness)
  -> structured scoring (occasion / style / colour / wardrobe reuse /
     relevance / budget efficiency)
  -> select best -> confidence -> explanation

Agent 4 never recomputes Agent 3's financials and never introduces a product
that was not present in validated Agent 2 / Agent 3 data.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.schemas.agent4_extensions import RejectReasonCode
from app.services.explanation_service import get_explanation_service
from app.services.validation_service import ValidationService, get_validation_service
from shared.schemas.agent2_schemas import ProductResult
from shared.schemas.agent3_schemas import (
    BudgetStatus,
    CandidateProductItem,
    OptimizationStrategy,
    OutfitOption,
)
from shared.schemas.agent4_schemas import (
    AlternativeOutfit,
    AlternativesResponse,
    BudgetOutcome,
    CandidateMetrics,
    ConfidenceLevel,
    DecisionAnalysisResponse,
    DecisionOutcome,
    DecisionRequest,
    DecisionResponse,
    DecisionStatus,
    EvaluatedCandidate,
    IssueSeverity,
    OutfitPiece,
    PieceSource,
    PurchaseSummary,
    ValidationIssue,
)

settings = get_settings()

_OCCASION_BASE = {"high": 0.9, "moderate": 0.6, "low": 0.35}


def _norm(token: Optional[str]) -> str:
    return (token or "").lower().strip().replace(" ", "_")


def _colour_near(piece_colour: str, preferred: str) -> bool:
    """Conservative colour match: exact, substring, or shared colour family."""
    pc, pf = piece_colour.lower(), preferred.lower()
    if not pc or not pf:
        return False
    if pc == pf or pc in pf or pf in pc:
        return True
    families = {
        "navy": ["blue", "dark"],
        "black": ["dark", "neutral"],
        "white": ["light", "neutral", "pastel"],
        "beige": ["neutral", "light", "tan", "cream"],
        "brown": ["neutral", "dark", "tan"],
        "grey": ["neutral"],
        "pink": ["bright", "pastel"],
        "red": ["bright"],
    }
    return pf in families.get(pc, []) or pc in families.get(pf, [])


# Requested garment type -> word variants that count as satisfying it.
# Conservative on purpose: a type is only matched when the product name or
# wardrobe item type actually contains the garment word (socks never match
# "heel", a plant pot matches nothing).
_TYPE_SYNONYMS: Dict[str, List[str]] = {
    "heel": ["heel", "pump", "stiletto", "kitten heel", "block heel", "court shoe"],
    "sandal": ["sandal", "slide", "flip flop"],
    "sneaker": ["sneaker", "trainer", "running shoe", "plimsoll"],
    "loafer": ["loafer", "moccasin"],
    "boot": ["boot", "ankle boot", "chelsea"],
    "slipper": ["slipper", "mule"],
    "shoe": ["shoe", "sneaker", "loafer", "flat", "heel", "boot", "sandal", "oxford", "derby"],
    "blouse": ["blouse", "shirt", "top"],
    "shirt": ["shirt", "blouse", "button"],
    "t-shirt": ["t shirt", "t-shirt", "tee"],
    "top": ["top", "blouse", "shirt", "tee"],
    "pant": ["pant", "trouser", "jean", "denim", "chino", "legging"],
    "trouser": ["trouser", "pant", "chino", "jean"],
    "jeans": ["jean", "denim"],
    "skirt": ["skirt"],
    "dress": ["dress", "frock", "gown"],
    "jacket": ["jacket", "coat", "blazer"],
    "coat": ["coat", "jacket"],
    "blazer": ["blazer", "jacket"],
    "hoodie": ["hoodie", "hooded"],
    "sweater": ["sweater", "jumper", "pullover", "cardigan", "hoodie"],
    "handbag": ["handbag", "bag", "purse", "tote", "satchel", "clutch"],
    "bag": ["bag", "handbag", "purse", "tote", "clutch"],
    "purse": ["purse", "handbag", "bag"],
    "scarf": ["scarf", "stole", "pashmina"],
    "hat": ["hat", "cap", "fedora", "beanie"],
    "belt": ["belt"],
    "watch": ["watch"],
    "earring": ["earring", "earring"],
    "necklace": ["necklace", "pendant"],
}


def _type_hit(piece: OutfitPiece, req_type: str) -> bool:
    t = _norm(req_type)
    if not t:
        return True
    hay = f"{piece.name or ''} {piece.type or ''}".lower()
    variants = _TYPE_SYNONYMS.get(t, [t])
    return any(re.search(rf"\b{re.escape(v)}", hay) for v in variants)


@dataclass
class EvaluatedOption:
    option: OutfitOption
    pieces: List[OutfitPiece]
    metrics: CandidateMetrics
    unresolved: List[str]
    passed: bool
    is_complete: bool
    rejection: Optional[str] = None
    trust_warnings: List[str] = field(default_factory=list)
    # (category, requested types, piece names that failed to match)
    type_mismatches: List[Tuple[str, List[str], List[str]]] = field(default_factory=list)
    # Machine-readable reason for `rejection` (Feature 2). Never changes whether
    # an option passed — it only labels the rejection that was already taken.
    rejection_codes: List[str] = field(default_factory=list)


class DecisionService:
    def __init__(self, validation_svc: Optional[ValidationService] = None):
        self.validation = validation_svc or get_validation_service(
            price_tolerance_usd=settings.PRICE_CONSISTENCY_TOLERANCE_USD
        )
        self.explanations = get_explanation_service()

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def decide(
        self, request: DecisionRequest
    ) -> Tuple[DecisionResponse, List[EvaluatedOption]]:
        issues, agent2_products, retrieval_provided = self.validation.validate_request(request)
        a1 = request.agent1_output
        a3 = request.budget_response
        ceiling = a3.budget_ceiling

        blocking = [i for i in issues if i.severity == IssueSeverity.ERROR
                    and i.code in ("request_id_mismatch",)]
        if blocking:
            resp = self._no_decision_response(request, issues, blocking[0].message)
            return resp, []

        required = [
            _norm(c) for c in a1.outfit_requirements.required_categories if _norm(c)
        ]
        prefs = self._preferred_colours(request)
        excluded = [_norm(c) for c in a1.user_requirements.excluded_colours if c]
        styles = [_norm(s) for s in a1.user_requirements.style if s]
        req_types = self._requested_types(request)

        evaluated = [
            self._evaluate(opt, request, required, prefs, excluded, styles,
                           agent2_products, retrieval_provided, req_types)
            for opt in a3.options
        ]

        feasible = [e for e in evaluated if e.passed]
        complete = [e for e in feasible if e.is_complete]
        ranked = sorted(complete or feasible, key=self._rank_key(request))

        if ranked:
            resp = self._finalize(request, ranked, issues, ceiling)
        else:
            resp = self._no_outfit_response(request, evaluated, issues)

        return resp, evaluated

    def analyze(self, request: DecisionRequest):
        resp, evaluated = self.decide(request)
        selected_id = resp.selected_combination_id
        candidates = [
            EvaluatedCandidate(
                combination_id=e.option.combination_id,
                strategy=e.option.strategy.value,
                name=e.option.name,
                total_cost_usd=e.option.cost_breakdown.total_cost,
                metrics=e.metrics,
                passed_hard_constraints=e.passed,
                rejection_reason=e.rejection,
                selected=(e.option.combination_id == selected_id),
            )
            for e in evaluated
        ]
        return DecisionAnalysisResponse(
            request_id=request.request_id,
            decision=resp.decision,
            validation_issues=resp.validation_issues,
            evaluated_candidates=candidates,
            unresolved_requirements=resp.unresolved_requirements,
        )

    def alternatives(self, request: DecisionRequest):
        resp, _ = self.decide(request)
        return AlternativesResponse(request_id=request.request_id, alternatives=resp.alternatives)

    # ------------------------------------------------------------------
    # Candidate evaluation
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        opt: OutfitOption,
        request: DecisionRequest,
        required: List[str],
        prefs: List[str],
        excluded: List[str],
        styles: List[str],
        agent2_products: Dict[str, ProductResult],
        retrieval_provided: bool,
        req_types: Dict[str, List[str]],
    ) -> EvaluatedOption:
        a1 = request.agent1_output
        wardrobe_by_id = {w.wardrobe_id: w for w in a1.wardrobe}

        pieces: List[OutfitPiece] = []
        trust_warnings: List[str] = []

        for w in opt.wardrobe_items_used:
            orig = wardrobe_by_id.get(w.wardrobe_id)
            pieces.append(
                OutfitPiece(
                    source=PieceSource.WARDROBE,
                    item_id=w.wardrobe_id,
                    category=_norm(w.category),
                    name=f"{w.colour} {w.type}".strip(),
                    colour=w.colour,
                    type=w.type,
                    price_usd=0.0,
                    role=w.repurpose_role or "Owned item reused",
                )
            )

        for cp in opt.selected_products:
            a2 = agent2_products.get(cp.product_id)
            pieces.append(
                OutfitPiece(
                    source=PieceSource.PURCHASE,
                    item_id=cp.product_id,
                    category=_norm(cp.category),
                    name=cp.name,
                    colour=cp.colour,
                    price_usd=cp.price,
                    store=cp.store,
                    url=cp.url,
                    availability=cp.availability,
                    relevance_score=cp.relevance_score,
                    role=f"Completes the {_norm(cp.category)} requirement",
                )
            )
            if a2 is not None and retrieval_provided and cp.price is None and a2.price is not None:
                trust_warnings.append(cp.product_id)

        # ---------- hard constraints (order = priority) ----------
        rejection: Optional[str] = None
        rejection_codes: List[str] = []

        untrustworthy = [
            cp.product_id
            for cp in opt.selected_products
            if not self.validation.candidate_is_trustworthy(
                cp, agent2_products, retrieval_provided
            )
        ]
        if untrustworthy:
            rejection = (
                "Contains products that could not be verified against the retrieved "
                "catalogue data: " + ", ".join(sorted(untrustworthy))
            )
            rejection_codes = [RejectReasonCode.CONSTRAINT_VIOLATION.value]

        if rejection is None:
            bad_colour = next(
                (
                    p.name
                    for p in pieces
                    if p.colour and any(self._excluded_hit(p.colour, ex) for ex in excluded)
                ),
                None,
            )
            if bad_colour:
                rejection = f"Includes '{bad_colour}', a colour the user asked to exclude"
                rejection_codes = [RejectReasonCode.STYLE_CLASH.value]

        if rejection is None and not opt.is_within_budget:
            rejection = "Over budget (budget feasibility comes from the purchase planner)"
            rejection_codes = [RejectReasonCode.OVER_BUDGET.value]

        if rejection is None:
            unavailable = [p.name for p in pieces if p.availability is False]
            if unavailable:
                rejection = "Contains unavailable item(s): " + ", ".join(unavailable[:3])
                rejection_codes = [RejectReasonCode.CONSTRAINT_VIOLATION.value]

        # ---------- completeness ----------
        covered = {p.category for p in pieces if p.category in required}
        unresolved = [c for c in required if c not in covered]
        is_complete = not unresolved

        # incompleteness is not a hard reject: it can still be the best
        # partial answer — but it can never win against a complete option
        # (handled by ranking).

        # ---------- structured scoring ----------
        metrics = self._score(
            opt, pieces, request, required, prefs, excluded, styles,
            agent2_products, unresolved,
        )

        # ---------- requested-type check (soft) ----------
        # A category can be covered yet still be wrong: crew socks do not
        # satisfy a requested "heel". Never a hard reject — a plausible
        # synonym gap shouldn't kill the outfit — but it lowers confidence
        # and ranks type-matching options above mismatching ones.
        type_mismatches: List[Tuple[str, List[str], List[str]]] = []
        for cat, types in req_types.items():
            if cat not in required or cat in unresolved:
                continue
            covering = [p for p in pieces if p.category == cat]
            if covering and not any(_type_hit(p, t) for p in covering for t in types):
                type_mismatches.append((cat, types, [p.name for p in covering]))

        passed = rejection is None
        return EvaluatedOption(
            option=opt,
            pieces=pieces,
            metrics=metrics,
            unresolved=unresolved,
            passed=passed,
            is_complete=is_complete,
            rejection=rejection,
            trust_warnings=trust_warnings,
            type_mismatches=type_mismatches,
            rejection_codes=rejection_codes,
        )

    # ------------------------------------------------------------------

    def _excluded_hit(self, colour: str, excluded_norm: str) -> bool:
        c = colour.lower()
        return bool(excluded_norm) and (excluded_norm in c or c in excluded_norm)

    def _requested_types(self, request: DecisionRequest) -> Dict[str, List[str]]:
        """Requested garment types per category, from Agent 1's identified items
        (role='requested'). Empty when the user only named categories."""
        out: Dict[str, List[str]] = {}
        for it in request.agent1_output.user_requirements.identified_items:
            if it.role != "requested":
                continue
            cat, typ = _norm(it.category), _norm(it.type)
            if not cat or not typ:
                continue
            if typ not in out.setdefault(cat, []):
                out[cat].append(typ)
        return out

    def _preferred_colours(self, request: DecisionRequest) -> List[str]:
        ur = request.agent1_output.user_requirements
        vals = [
            *(c.lower().strip() for c in ur.colour_preferences if c),
            *(
                it.colour.lower().strip()
                for it in ur.identified_items
                if it.colour and it.role == "requested"
            ),
        ]
        return list(dict.fromkeys(v for v in vals if v))

    def _score(
        self,
        opt: OutfitOption,
        pieces: List[OutfitPiece],
        request: DecisionRequest,
        required: List[str],
        prefs: List[str],
        excluded: List[str],
        styles: List[str],
        agent2_products: Dict[str, ProductResult],
        unresolved: List[str],
    ) -> CandidateMetrics:
        a1 = request.agent1_output

        # occasion: Agent 1's wardrobe-level judgement, tempered by the
        # style-match of the retrieved products actually purchased.
        base = 0.5
        if a1.compatibility and a1.compatibility.occasion_suitability in _OCCASION_BASE:
            base = _OCCASION_BASE[a1.compatibility.occasion_suitability]
        prod_style = [
            agent2_products[p.item_id].score_breakdown.style_match
            for p in pieces
            if p.source == PieceSource.PURCHASE and p.item_id in agent2_products
        ]
        occasion_fit = round(
            (0.5 * base + 0.5 * (sum(prod_style) / len(prod_style))) if prod_style else base, 3
        )

        # style fit per piece
        style_vals: List[float] = []
        wardrobe_by_id = {w.wardrobe_id: w for w in a1.wardrobe}
        for p in pieces:
            if p.source == PieceSource.PURCHASE:
                a2 = agent2_products.get(p.item_id)
                style_vals.append(a2.score_breakdown.style_match if a2 else (p.relevance_score or 0.5))
            else:
                orig = wardrobe_by_id.get(p.item_id)
                if not styles:
                    style_vals.append(0.75)
                elif orig and _norm(orig.style) in styles:
                    style_vals.append(1.0)
                else:
                    style_vals.append(0.5 if orig else 0.6)
        style_fit = round(sum(style_vals) / len(style_vals), 3) if style_vals else 0.5

        # colour fit per piece
        colour_vals: List[float] = []
        for p in pieces:
            if not prefs:
                colour_vals.append(0.75)
                continue
            if any(self._excluded_hit(p.colour or "", ex) for ex in excluded):
                colour_vals.append(0.0)
                continue
            if p.source == PieceSource.PURCHASE and p.item_id in agent2_products:
                colour_vals.append(agent2_products[p.item_id].score_breakdown.colour_match)
                continue
            pc = (p.colour or "").lower()
            colour_vals.append(
                1.0 if any(_colour_near(pc, pref) for pref in prefs) else 0.4
            )
        colour_fit = round(sum(colour_vals) / len(colour_vals), 3) if colour_vals else 0.5

        # wardrobe reuse: share of required categories covered by owned items
        if required:
            owned_cats = {p.category for p in pieces if p.source == PieceSource.WARDROBE}
            wardrobe_reuse = round(len(owned_cats & set(required)) / len(required), 3)
        else:
            wardrobe_reuse = 1.0

        purchased = [p for p in pieces if p.source == PieceSource.PURCHASE]
        retrieval_relevance = (
            round(sum(p.relevance_score or 0.5 for p in purchased) / len(purchased), 3)
            if purchased
            else 1.0
        )

        decision_score = round(
            settings.W_OCCASION * occasion_fit
            + settings.W_STYLE * style_fit
            + settings.W_COLOUR * colour_fit
            + settings.W_WARDROBE_REUSE * wardrobe_reuse
            + settings.W_RELEVANCE * retrieval_relevance
            + settings.W_BUDGET * opt.budget_efficiency_score,
            4,
        )

        return CandidateMetrics(
            occasion_fit=occasion_fit,
            style_fit=style_fit,
            colour_fit=colour_fit,
            wardrobe_reuse=wardrobe_reuse,
            retrieval_relevance=retrieval_relevance,
            budget_efficiency=round(opt.budget_efficiency_score, 3),
            purchase_count=len(purchased),
            within_budget=opt.is_within_budget,
            is_complete=not unresolved,
            decision_score=min(max(decision_score, 0.0), 1.0),
        )

    def _rank_key(self, request: DecisionRequest):
        def key(e: EvaluatedOption):
            m = e.metrics
            secondary = (
                len(e.type_mismatches),
                m.purchase_count,
                e.option.cost_breakdown.total_cost,
            )
            return (-m.decision_score, *secondary, e.option.combination_id)

        return key

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(
        self,
        request: DecisionRequest,
        ranked: List[EvaluatedOption],
        issues: List[ValidationIssue],
        ceiling: float,
    ) -> DecisionResponse:
        best = ranked[0]
        opt = best.option
        cb = opt.cost_breakdown
        status = (
            DecisionStatus.COMPLETE if best.is_complete else DecisionStatus.PARTIAL
        )

        confidence_score, confidence_level = self._confidence(best, request, issues, ranked)

        alternatives = [self._alternative(e, best) for e in ranked[1:4]]

        explanation = self.explanations.build(
            request=request,
            chosen=best,
            alternatives=[e for e in ranked[1:]],
            issues=issues,
        )

        all_issues = list(issues)
        if best.type_mismatches:
            for cat, types, names in best.type_mismatches:
                all_issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="type_mismatch",
                        message=(
                            f"No {cat} item matches the requested type "
                            + "/".join(f"'{t}'" for t in types)
                        ),
                        field=cat,
                    )
                )
            notes = [
                f"the {cat} pick \u201c{names[0]}\u201d may not be the requested "
                + "/".join(f"'{t}'" for t in types)
                for cat, types, names in best.type_mismatches
            ]
            explanation += " Note: " + "; ".join(notes) + "."

        return DecisionResponse(
            request_id=request.request_id,
            decision=DecisionOutcome(
                status=status,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
            ),
            selected_combination_id=opt.combination_id,
            strategy=opt.strategy.value,
            outfit=best.pieces,
            budget=BudgetOutcome(
                maximum_usd=cb.budget_ceiling,
                additional_cost_usd=cb.total_cost,
                remaining_usd=cb.budget_remaining,
                within_budget=opt.is_within_budget,
            ),
            purchase_summary=PurchaseSummary(
                purchase_count=sum(1 for p in best.pieces if p.source == PieceSource.PURCHASE),
                existing_items_used=sum(1 for p in best.pieces if p.source == PieceSource.WARDROBE),
            ),
            metrics=best.metrics,
            alternatives=alternatives,
            unresolved_requirements=best.unresolved,
            explanation=explanation,
            validation_issues=all_issues,
        )

    def _alternative(self, e: EvaluatedOption, best: EvaluatedOption) -> AlternativeOutfit:
        reasons: List[str] = []
        m, b = e.metrics, best.metrics
        if m.purchase_count < b.purchase_count:
            reasons.append(f"adds {b.purchase_count - m.purchase_count} fewer new item(s)")
        cost_d = best.option.cost_breakdown.total_cost - e.option.cost_breakdown.total_cost
        if cost_d > 0.005:
            reasons.append(f"saves USD {cost_d:,.2f}")
        if m.retrieval_relevance > b.retrieval_relevance:
            reasons.append("higher product relevance")
        if not e.is_complete:
            reasons.append("incomplete: missing " + ", ".join(e.unresolved))
        return AlternativeOutfit(
            combination_id=e.option.combination_id,
            strategy=e.option.strategy.value,
            name=e.option.name,
            total_cost_usd=e.option.cost_breakdown.total_cost,
            within_budget=e.option.is_within_budget,
            decision_score=m.decision_score,
            reason="; ".join(reasons) if reasons else "also fits your constraints",
        )

    def _confidence(
        self,
        best: EvaluatedOption,
        request: DecisionRequest,
        issues: List[ValidationIssue],
        ranked: List[EvaluatedOption],
    ) -> Tuple[float, ConfidenceLevel]:
        required = [_norm(c) for c in request.agent1_output.outfit_requirements.required_categories]
        coverage = 1.0
        if required:
            coverage = (len(required) - len(best.unresolved)) / len(required)

        avail_known = [p.availability for p in best.pieces if p.source == PieceSource.PURCHASE]
        availability_term = 1.0 if all(a is True for a in avail_known) else 0.4

        retrieval_provided = any(
            r and r.results for r in (request.retrieval_by_category or {}).values()
        )
        input_term = 1.0 if retrieval_provided else 0.3

        score = (
            0.35 * coverage
            + 0.35 * best.metrics.decision_score
            + 0.15 * (1.0 if best.option.is_within_budget else 0.0)
            + 0.10 * availability_term
            + 0.05 * input_term
        )

        warnings = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        score -= min(warnings * 0.03, 0.15)

        if not best.is_complete:
            score = min(score, 0.65)

        if best.type_mismatches:
            # covered category, wrong garment (socks for heels) — never "high"
            score = min(score, 0.65)

        score = round(min(max(score, 0.0), 0.98), 2)
        level = (
            ConfidenceLevel.HIGH if score >= 0.75
            else ConfidenceLevel.MEDIUM if score >= 0.5
            else ConfidenceLevel.LOW
        )
        return score, level

    # ------------------------------------------------------------------

    def _empty_budget(self, ceiling: float, within: bool = False) -> BudgetOutcome:
        return BudgetOutcome(
            maximum_usd=ceiling,
            additional_cost_usd=0.0,
            remaining_usd=ceiling,
            within_budget=within,
        )

    def _no_outfit_response(
        self,
        request: DecisionRequest,
        evaluated: List[EvaluatedOption],
        issues: List[ValidationIssue],
    ) -> DecisionResponse:
        a3 = request.budget_response
        required = [_norm(c) for c in request.agent1_output.outfit_requirements.required_categories]
        explanation = self.explanations.build_no_outfit(request, evaluated)
        return DecisionResponse(
            request_id=request.request_id,
            decision=DecisionOutcome(
                status=DecisionStatus.NO_SUITABLE_OUTFIT,
                confidence_score=0.25,
                confidence_level=ConfidenceLevel.LOW,
            ),
            budget=self._empty_budget(a3.budget_ceiling),
            purchase_summary=PurchaseSummary(purchase_count=0, existing_items_used=0),
            unresolved_requirements=required,
            explanation=explanation,
            validation_issues=issues,
        )

    def _no_decision_response(
        self, request: DecisionRequest, issues: List[ValidationIssue], reason: str
    ) -> DecisionResponse:
        return DecisionResponse(
            request_id=request.request_id,
            decision=DecisionOutcome(
                status=DecisionStatus.INSUFFICIENT_INPUT,
                confidence_score=0.05,
                confidence_level=ConfidenceLevel.LOW,
            ),
            budget=self._empty_budget(request.budget_response.budget_ceiling),
            purchase_summary=PurchaseSummary(purchase_count=0, existing_items_used=0),
            unresolved_requirements=[
                _norm(c) for c in request.agent1_output.outfit_requirements.required_categories
            ],
            explanation=f"Could not make a decision: {reason}",
            validation_issues=issues,
        )


_decision_service: Optional[DecisionService] = None


def get_decision_service() -> DecisionService:
    global _decision_service
    if _decision_service is None:
        _decision_service = DecisionService()
    return _decision_service
