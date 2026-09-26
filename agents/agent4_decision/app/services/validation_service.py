"""
Input validation for Agent 4.

Validates the three upstream payloads BEFORE any decision is made:
- request_id correlation across Agents 1/2/3
- every purchased product genuinely exists in Agent 2's retrieval (hallucination guard)
- price / availability / category consistency between Agent 2 and Agent 3
  (inconsistencies are FLAGGED, never silently resolved in favour of one side)
- wardrobe references resolve to real owned items
- basic field sanity (numeric prices, known categories)
"""

from typing import Dict, List, Optional, Tuple

from shared.constants import ProductCategory
from shared.schemas.agent2_schemas import ProductResult
from shared.schemas.agent3_schemas import CandidateProductItem, WardrobeRepurposedItem
from shared.schemas.agent4_schemas import DecisionRequest, IssueSeverity, ValidationIssue

_VALID_CATEGORIES = {c.value for c in ProductCategory}


def _cat(value) -> str:
    """Category as its bare value string — enums and plain strings coexist
    across payloads (Agent 3 uses Union[ProductCategory, str])."""
    return str(getattr(value, "value", value) or "").lower().strip()

# (issues, agent2 product lookup, whether any Agent 2 data was supplied)
ValidationReport = Tuple[
    List[ValidationIssue], Dict[str, ProductResult], bool
]


class ValidationService:
    """Cross-agent consistency checks over already-Pydantic-validated payloads."""

    def __init__(self, price_tolerance_usd: float = 0.5):
        self.price_tolerance = price_tolerance_usd

    # ------------------------------------------------------------------

    def validate_request(self, request: DecisionRequest) -> ValidationReport:
        issues: List[ValidationIssue] = []
        a1 = request.agent1_output
        a3 = request.budget_response

        # 1. Correlation: every payload must belong to the same session.
        ids = {"request": request.request_id, "agent1": a1.request_id, "budget": a3.request_id}
        if len(set(ids.values())) > 1:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="request_id_mismatch",
                    message=(
                        "Correlation IDs disagree across agents: "
                        + ", ".join(f"{k}={v}" for k, v in ids.items())
                    ),
                )
            )

        # 2. Agent 2 product lookup (the authoritative catalogue of real products).
        agent2_products: Dict[str, ProductResult] = {}
        retrieval_provided = False
        for cat_key, resp in (request.retrieval_by_category or {}).items():
            if not resp or not resp.results:
                continue
            retrieval_provided = True
            if resp.request_id != request.request_id:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="retrieval_request_id_mismatch",
                        message=(
                            f"Agent 2 response for '{cat_key}' carries request_id "
                            f"{resp.request_id}, expected {request.request_id}."
                        ),
                    )
                )
            for p in resp.results:
                agent2_products.setdefault(p.product_id, p)

        # 3. Every purchased product in every budget option must be genuine
        #    and consistent between Agent 2 and Agent 3. Keyed by (id, price)
        #    so the SAME product priced differently across options is still
        #    cross-checked — a stale second copy must not be deduped away.
        seen_ids: set = set()
        for opt in a3.options:
            for cp in opt.selected_products:
                issues.extend(
                    self._check_product(cp, cat_hint=None, agent2_products=agent2_products,
                                        retrieval_provided=retrieval_provided, seen_ids=seen_ids)
                )

        # 4. Wardrobe references must resolve to owned items.
        wardrobe_ids = {w.wardrobe_id for w in a1.wardrobe}
        for opt in a3.options:
            for w in opt.wardrobe_items_used:
                if w.wardrobe_id not in wardrobe_ids:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.WARNING,
                            code="unknown_wardrobe_reference",
                            message=(
                                f"Budget option '{opt.combination_id}' references wardrobe item "
                                f"{w.wardrobe_id}, which is not in the user's wardrobe."
                            ),
                            field="wardrobe_id",
                        )
                    )

        return issues, agent2_products, retrieval_provided

    # ------------------------------------------------------------------

    def candidate_is_trustworthy(
        self,
        product: CandidateProductItem,
        agent2_products: Dict[str, ProductResult],
        retrieval_provided: bool,
    ) -> bool:
        """A candidate containing an unvalidated or inconsistent product cannot be chosen."""
        if not retrieval_provided:
            return True
        a2 = agent2_products.get(product.product_id)
        if a2 is None:
            return False
        if a2.price is not None and product.price is not None:
            if abs(a2.price - product.price) > self.price_tolerance:
                return False
        return True

    # ------------------------------------------------------------------

    def _check_product(
        self,
        cp: CandidateProductItem,
        cat_hint: Optional[str],
        agent2_products: Dict[str, ProductResult],
        retrieval_provided: bool,
        seen_ids: set,
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        if (cp.product_id, cp.price) in seen_ids:
            return issues
        seen_ids.add((cp.product_id, cp.price))

        if not isinstance(cp.price, (int, float)) or cp.price < 0:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="invalid_price",
                    message=f"Product {cp.product_id} has a non-numeric or negative price.",
                    product_id=cp.product_id,
                    field="price",
                )
            )

        cat_val = _cat(cat_hint) or _cat(cp.category)
        if cat_val and cat_val not in _VALID_CATEGORIES:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="unknown_category",
                    message=f"Product {cp.product_id} has unrecognized category '{cp.category}'.",
                    product_id=cp.product_id,
                    field="category",
                )
            )

        if not retrieval_provided:
            return issues

        a2 = agent2_products.get(cp.product_id)
        if a2 is None:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="unvalidated_product",
                    message=(
                        f"Budget plan includes product {cp.product_id} ('{cp.name}') that Agent 2 "
                        "never returned — it cannot be recommended."
                    ),
                    product_id=cp.product_id,
                )
            )
            return issues

        if a2.price is not None and cp.price is not None and abs(a2.price - cp.price) > self.price_tolerance:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="price_inconsistency",
                    message=(
                        f"Product {cp.product_id}: Agent 2 lists USD {a2.price:,.2f} but the budget "
                        f"plan uses USD {cp.price:,.2f}. The disagreement is flagged, not silently resolved."
                    ),
                    product_id=cp.product_id,
                    field="price",
                )
            )

        if a2.availability != cp.availability:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="availability_mismatch",
                    message=(
                        f"Product {cp.product_id}: availability differs between Agent 2 "
                        f"({a2.availability}) and the budget plan ({cp.availability})."
                    ),
                    product_id=cp.product_id,
                    field="availability",
                )
            )

        if _cat(a2.category) and _cat(cp.category) and _cat(a2.category) != _cat(cp.category):
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="category_mismatch",
                    message=(
                        f"Product {cp.product_id}: category differs between Agent 2 "
                        f"({a2.category}) and the budget plan ({cp.category})."
                    ),
                    product_id=cp.product_id,
                    field="category",
                )
            )

        return issues


_validation_service: Optional[ValidationService] = None


def get_validation_service(price_tolerance_usd: float = 0.5) -> ValidationService:
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService(price_tolerance_usd=price_tolerance_usd)
    return _validation_service
