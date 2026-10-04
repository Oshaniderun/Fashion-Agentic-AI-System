"""
Feature 4 — counterfactual analysis (deterministic re-scoring, never an LLM).

Answers "what would have had to be different?" by re-running the real decision
engine on hypothetical inputs:

  * the smallest budget increase that would hand the win to a runner-up
    (or the honest statement that no increase within the search bound would)
  * a single product substitution that flips the decision
  * which reported sub-score explains that flip

The probes are throwaway: only ``selected_combination_id`` is read back, and no
probe answer is ever returned as a recommendation.
"""

from typing import List, Optional, Sequence, Tuple

from app.core.config import get_settings
from app.schemas.agent4_extensions import Counterfactual, CounterfactualKind
from app.services.decision_service import DecisionService, EvaluatedOption
from app.services.score_breakdown_service import build_breakdown
from shared.schemas.agent2_schemas import ProductResult
from shared.schemas.agent4_schemas import DecisionRequest, DecisionResponse, PieceSource

settings = get_settings()

_BUDGET_FIELD = "budget_response.budget_ceiling"


def _usd(amount: float) -> str:
    return f"USD {amount:,.2f}"


def _budget_probe(request: DecisionRequest, ceiling: float) -> DecisionRequest:
    """Same request with a larger ceiling; feasibility follows from it."""
    a3 = request.budget_response
    options = [
        opt.model_copy(
            update={"is_within_budget": opt.cost_breakdown.total_cost <= ceiling}
        )
        for opt in a3.options
    ]
    return request.model_copy(
        update={
            "budget_response": a3.model_copy(
                update={"budget_ceiling": ceiling, "options": options}
            )
        }
    )


def _swap_probe(
    request: DecisionRequest,
    combination_id: str,
    old_id: str,
    replacement: ProductResult,
) -> DecisionRequest:
    """Same request with one purchased product swapped inside one option."""
    a3 = request.budget_response
    options = []
    for opt in a3.options:
        if opt.combination_id != combination_id:
            options.append(opt)
            continue
        products = []
        for cp in opt.selected_products:
            if cp.product_id != old_id:
                products.append(cp)
                continue
            products.append(
                cp.model_copy(
                    update={
                        "product_id": replacement.product_id,
                        "name": replacement.name,
                        "colour": replacement.colour,
                        "price": replacement.price,
                        "store": replacement.store,
                        "relevance_score": replacement.relevance_score,
                        "availability": replacement.availability,
                    }
                )
            )
        total = round(sum(p.price or 0.0 for p in products), 2)
        cb = opt.cost_breakdown
        options.append(
            opt.model_copy(
                update={
                    "selected_products": products,
                    "is_within_budget": total <= cb.budget_ceiling,
                    "cost_breakdown": cb.model_copy(
                        update={
                            "total_cost": total,
                            "budget_remaining": round(cb.budget_ceiling - total, 2),
                        }
                    ),
                }
            )
        )
    return request.model_copy(update={"budget_response": a3.model_copy(update={"options": options})})


def _winner(service: DecisionService, probe: DecisionRequest):
    response, evaluated = service.decide(probe)
    return response, evaluated


def _flip_sub_score(
    probe: DecisionRequest,
    probe_response: DecisionResponse,
    probe_evaluated: List[EvaluatedOption],
    winner_id: str,
    loser_id: str,
) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """Which reported sub-score most separates the new winner from the old one."""
    ranked = [
        e
        for e in probe_evaluated
        if e.option.combination_id in (winner_id, loser_id)
    ]
    if len(ranked) < 2:
        return None, None, None
    breakdowns = build_breakdown(probe, ranked, probe_response.validation_issues)
    by_id = {b.combination_id: b for b in breakdowns}
    win, lose = by_id.get(winner_id), by_id.get(loser_id)
    if win is None or lose is None:
        return None, None, None
    deltas = {
        key: getattr(win.sub_scores, key) - getattr(lose.sub_scores, key)
        for key in win.sub_scores.model_dump()
    }
    name = max(sorted(deltas), key=lambda k: abs(deltas[k]))
    return name, getattr(win.sub_scores, name), getattr(lose.sub_scores, name)


def _budget_counterfactuals(
    request: DecisionRequest,
    response: DecisionResponse,
    service: DecisionService,
) -> List[Counterfactual]:
    ceiling = request.budget_response.budget_ceiling
    limit = ceiling + settings.COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD
    chosen = response.selected_combination_id
    points = sorted(
        {
            round(float(o.cost_breakdown.total_cost), 2)
            for o in request.budget_response.options
            if ceiling < round(float(o.cost_breakdown.total_cost), 2) <= limit
        }
    )
    for probe_ceiling in points:
        probe = _budget_probe(request, probe_ceiling)
        probe_response, probe_evaluated = _winner(service, probe)
        winner = probe_response.selected_combination_id
        if winner and winner != chosen:
            sub, hi, lo = _flip_sub_score(
                probe, probe_response, probe_evaluated, winner, chosen
            )
            sentence = (
                f"Raising the budget from {_usd(ceiling)} to {_usd(probe_ceiling)} would make "
                f"{winner} the better answer than {chosen}."
            )
            if sub:
                sentence += " The gap is widest on " + _human(sub) + f" ({_pct(hi)} against {_pct(lo)})."
            return [
                Counterfactual(
                    kind=CounterfactualKind.BUDGET_INCREASE,
                    field=_BUDGET_FIELD,
                    old_value=ceiling,
                    new_value=probe_ceiling,
                    resulting_winner=winner,
                    sub_score=sub,
                    sentence=sentence,
                )
            ]
    return [
        Counterfactual(
            kind=CounterfactualKind.NO_BUDGET_CHANGE,
            field=_BUDGET_FIELD,
            old_value=ceiling,
            new_value=None,
            resulting_winner=chosen,
            sentence=(
                f"No budget increase up to {_usd(limit)} would change this result — "
                f"{chosen} stays the best answer on the current data."
            ),
        )
    ]


def _human(key: str) -> str:
    return key.replace("_", " ")


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{round(value, 2):.2f}"


def _swap_candidates(request: DecisionRequest) -> List[ProductResult]:
    seen = set()
    out: List[ProductResult] = []
    for items in (request.retrieval_by_category or {}).values():
        for product in items.results or []:
            if product.product_id in seen:
                continue
            seen.add(product.product_id)
            out.append(product)
    return sorted(out, key=lambda p: (_cat(p), p.product_id))


def _swap_counterfactuals(
    request: DecisionRequest,
    response: DecisionResponse,
    evaluated: List[EvaluatedOption],
    service: DecisionService,
) -> List[Counterfactual]:
    chosen_id = response.selected_combination_id
    chosen = next((e for e in evaluated if e.option.combination_id == chosen_id), None)
    if chosen is None:
        return []
    inside = {p.item_id for p in chosen.pieces if p.source == PieceSource.PURCHASE}
    purchased = [p for p in chosen.pieces if p.source == PieceSource.PURCHASE]
    pool = _swap_candidates(request)

    probes = 0
    for piece in sorted(purchased, key=lambda p: p.item_id):
        replacements = [
            product
            for product in pool
            if product.product_id not in inside
            and _cat(product) == piece.category
            and product.availability is not False
        ]
        for product in replacements:
            if probes >= settings.COUNTERFACTUAL_MAX_SWAP_PROBES:
                return []
            probes += 1
            probe = _swap_probe(request, chosen_id, piece.item_id, product)
            probe_response, probe_evaluated = _winner(service, probe)
            winner = probe_response.selected_combination_id
            if winner and winner != chosen_id:
                sub, hi, lo = _flip_sub_score(
                    probe, probe_response, probe_evaluated, winner, chosen_id
                )
                sentence = (
                    f"Swapping {piece.item_id} for {product.product_id} in {chosen_id} would "
                    f"hand the decision to {winner}."
                )
                if sub:
                    sentence += (
                        " The deciding axis is " + _human(sub)
                        + f" ({_pct(hi)} against {_pct(lo)})."
                    )
                return [
                    Counterfactual(
                        kind=CounterfactualKind.ITEM_SWAP,
                        field=f"options[{chosen_id}].products[{piece.item_id}]",
                        old_value=piece.item_id,
                        new_value=product.product_id,
                        resulting_winner=winner,
                        sub_score=sub,
                        sentence=sentence,
                    )
                ]
    return []


def _cat(product: ProductResult) -> str:
    value = product.category
    return (getattr(value, "value", None) or str(value)).lower().strip()


def build(
    request: DecisionRequest,
    response: DecisionResponse,
    evaluated: List[EvaluatedOption],
    *,
    service: Optional[DecisionService] = None,
    skip: bool = False,
) -> List[Counterfactual]:
    """Up to MAX_COUNTERFACTUALS machine-readable 'what would change the answer' notes."""
    if service is None or skip or not response.selected_combination_id:
        return []
    out = _budget_counterfactuals(request, response, service)
    out += _swap_counterfactuals(request, response, evaluated, service)
    return out[: settings.MAX_COUNTERFACTUALS]
