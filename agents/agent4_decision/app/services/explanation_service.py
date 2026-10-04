"""
Deterministic explanation builder for Agent 4.

Every number in the narrative comes from the upstream data (the purchase
planner's financials, the catalogue's prices) — the explanation never
invents values, items, or percentages. It is the floor; the optional Gemini
polish layer only rewrites this text, never the decision.
"""

from typing import TYPE_CHECKING, List, Optional

from shared.schemas.agent4_schemas import DecisionRequest, IssueSeverity, PieceSource

if TYPE_CHECKING:  # avoid a circular import with decision_service
    from app.services.decision_service import EvaluatedOption


def _usd(amount: Optional[float]) -> str:
    if amount is None:
        return "price not listed"
    return f"USD {amount:,.2f}"


def _clip(text: Optional[str], n: int = 60) -> str:
    return (text or "")[:n].strip()


def _plural(items) -> str:
    return "" if len(items) == 1 else "s"


class ExplanationService:
    """Plain-language rationale assembled from validated fields only."""

    def build(
        self,
        request: DecisionRequest,
        chosen: "EvaluatedOption",
        alternatives: List["EvaluatedOption"],
        issues: List,
    ) -> str:
        opt = chosen.option
        cb = opt.cost_breakdown
        pieces = chosen.pieces
        purchases = [p for p in pieces if p.source == PieceSource.PURCHASE]
        owned = [p for p in pieces if p.source == PieceSource.WARDROBE]

        sentences: List[str] = []

        # 1. What this option is
        owned_part = (
            f" It reuses {len(owned)} item{_plural(owned)} from your wardrobe"
            + (f" ({_clip(owned[0].name)}"
               + (f" and {len(owned) - 1} more" if len(owned) > 1 else "")
               + ")" if owned else "")
            + "."
            if owned
            else ""
        )
        sentences.append(f"Selected \u201c{_clip(opt.name, 80)}\u201d.{owned_part}")

        # 2. What is bought and from where
        if purchases:
            buys = "; ".join(
                f"{_clip(p.name)} ({_usd(p.price_usd)}"
                + (f", {_clip(p.store, 30)}" if p.store else "")
                + ")"
                for p in purchases[:3]
            )
            sentences.append(f"New items: {buys}.")
        else:
            sentences.append("No new purchases are needed for this option.")

        # 3. Financials — verbatim from the purchase planner
        if cb.total_cost > 0:
            sentences.append(
                f"The total additional cost is {_usd(cb.total_cost)} against your "
                f"{_usd(cb.budget_ceiling)} budget, leaving {_usd(cb.budget_remaining)} to spare."
            )
        else:
            sentences.append(
                f"This outfit costs nothing extra, well within your {_usd(cb.budget_ceiling)} budget."
            )

        # 4. Fit rationale (from the scoring signals, no invented specifics)
        fit = self._fit_sentence(request, chosen)
        if fit:
            sentences.append(fit)

        # 5. Honest partial result
        if not chosen.is_complete:
            sentences.append(
                "Note: this outfit does not yet cover every requirement — still missing: "
                + ", ".join(chosen.unresolved)
                + ". Nothing was invented to fill the gap."
            )

        # 6. Trade-off vs the runner-up
        if alternatives:
            runner = alternatives[0]
            # Positive diff means the runner-up costs MORE than the chosen option.
            diff_cost = runner.option.cost_breakdown.total_cost - cb.total_cost
            if abs(diff_cost) >= 0.005:
                side = "more expensive" if diff_cost > 0 else "cheaper"
                sentences.append(
                    f"The next-best alternative (\u201c{_clip(runner.option.name, 60)}\u201d) is "
                    f"{_usd(abs(diff_cost))} {side} but matched your style and colour preferences less well."
                )
            elif runner.metrics.purchase_count > len(purchases):
                sentences.append(
                    "It was chosen over a same-price alternative because it needs fewer new items."
                )

        # 7. Flagged inconsistencies, if any touch the chosen option
        chosen_issue = next(
            (i for i in issues
             if getattr(i, "severity", None) == IssueSeverity.WARNING
             and getattr(i, "code", "") in ("availability_mismatch", "category_mismatch")),
            None,
        )
        if chosen_issue:
            sentences.append("One detail differs between sources and was double-checked before choosing.")

        return " ".join(sentences)

    # ------------------------------------------------------------------

    def build_no_outfit(
        self, request: DecisionRequest, evaluated: List["EvaluatedOption"]
    ) -> str:
        if not evaluated:
            return (
                "The purchase plan contained no outfit options to evaluate, "
                "so no recommendation could be made."
            )
        reasons: List[str] = []
        for e in evaluated[:3]:
            reason = e.rejection or (
                "missing " + ", ".join(e.unresolved) if not e.is_complete else "scored lowest"
            )
            reasons.append(f"\u201c{_clip(e.option.name, 50)}\u201d ({reason})")
        return (
            "None of the proposed plans could be recommended: "
            + "; ".join(reasons)
            + ". Widening the budget or relaxing a preference would open up more options."
        )

    # ------------------------------------------------------------------

    def _fit_sentence(self, request: DecisionRequest, chosen: "EvaluatedOption") -> str:
        ur = request.agent1_output.user_requirements
        m = chosen.metrics
        parts: List[str] = []
        prefs = [c for c in (
            list(ur.colour_preferences)
            + [it.colour for it in ur.identified_items if it.colour and it.role == "requested"]
        ) if c]
        if prefs and m.colour_fit >= 0.7:
            parts.append(f"matches your {'/'.join(prefs[:2]).lower()} colour preference")
        elif m.colour_fit >= 0.7:
            parts.append("uses colours that suit your existing items")
        if ur.style and m.style_fit >= 0.7:
            parts.append(f"fits the {ur.style[0].replace('_', ' ')} style you asked for")
        if ur.occasion and m.occasion_fit >= 0.7:
            parts.append(f"is appropriate for {ur.occasion.replace('_', ' ')}")
        if m.within_budget and m.budget_efficiency >= 0.7 and m.purchase_count:
            parts.append("keeps most of your budget untouched")
        if not parts:
            return ""
        return "This option " + ", ".join(parts[:-1]) + (f" and {parts[-1]}" if len(parts) > 1 else parts[0]) + "."


_explanation_service: Optional[ExplanationService] = None


def get_explanation_service() -> ExplanationService:
    global _explanation_service
    if _explanation_service is None:
        _explanation_service = ExplanationService()
    return _explanation_service
