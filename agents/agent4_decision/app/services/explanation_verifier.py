"""
Feature 3 — explanation faithfulness verification (deterministic).

The narrative Agent 4 returns must contain nothing that is absent from the
validated upstream payloads. This verifier treats the explanation as an
untrusted string (whether it came from the template or from Gemini) and checks
it against the data the decision was actually made from:

  * every money amount appears on a real candidate/option (or is the exact
    difference between two real option totals)
  * the total / ceiling / remaining figures quoted together add up
  * every quoted name exists in the data
  * every colour word belongs to an outfit piece or a user-stated colour
  * no percentages, discounts or "free"-type claims, and no retailer that is
    not one of the stores in the data

Nothing here re-decides the outfit: on failure the caller discards the polished
text and keeps the deterministic template, then reports what was found.
"""

from dataclasses import dataclass, field
import re
from typing import Iterable, List, Sequence, Set

from app.core.config import get_settings
from shared.schemas.agent4_schemas import DecisionRequest

settings = get_settings()

_MONEY = "USD"
_AMOUNT_RE = re.compile(rf"(?:{_MONEY}|\$)\s*([0-9][\d,]*(?:\.[0-9]{{1,2}})?)")
_LEAVING_RE = re.compile(r"leaving[^.]*?(?:USD|\$)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b")
_QUOTED_RE = re.compile(r"[\u201c\"]([^\u201d\"]{1,160})[\u201d\"]")

# Words that turn a grounded explanation into a promotion we cannot verify.
_FORBIDDEN_TERMS = (
    "%",
    "percent",
    "discount",
    "voucher",
    "coupon",
    "promo",
    "free shipping",
    "buy one",
    "half price",
    "flash sale",
    "clearance",
)

# Retailers a language model is prone to name-drop. Only flagged when the name
# is genuinely absent from the supplied data. Common English words are excluded
# from this list on purpose ("next", "target") so honest prose is not flagged.
_WATCHED_RETAILERS = (
    "amazon",
    "asos",
    "zara",
    "h&m",
    "shein",
    "john lewis",
    "m&s",
    "marks & spencer",
    "topshop",
    "nordstrom",
    "macy",
    "uniqlo",
    "zalando",
    "boohoo",
    "nike",
    "adidas",
)

# Words that read as colours in this domain; checked, not counted.
_COLOUR_WORDS = (
    "black", "white", "ivory", "cream", "beige", "tan", "brown", "grey", "gray",
    "navy", "blue", "red", "maroon", "green", "olive", "yellow", "gold", "golden",
    "pink", "rose", "purple", "lilac", "violet", "orange", "coral", "turquoise",
    "teal", "mint", "burgundy", "charcoal", "silver", "khaki", "denim", "multicolour",
    "multicolor", "pastel",
)

@dataclass
class VerificationResult:
    verified: bool
    issues: List[str] = field(default_factory=list)


def _clip(text: str) -> str:
    return (text or "")[: settings.VERIFICATION_ISSUE_TEXT_LIMIT].strip()


def _fmt(value: float) -> str:
    return f"{round(value, 2):.2f}"


def _amounts_in_data(request: DecisionRequest, outfit_pieces: Sequence) -> Set[float]:
    """Every price/total that legitimately exists, plus real pairwise deltas."""
    amounts: Set[float] = {0.0}
    a3 = request.budget_response
    amounts.add(round(float(a3.budget_ceiling), 2))
    totals: List[float] = []
    for opt in a3.options:
        cb = opt.cost_breakdown
        for value in (cb.total_cost, cb.budget_ceiling, cb.budget_remaining):
            if value is not None:
                amounts.add(round(abs(float(value)), 2))
        totals.append(round(float(cb.total_cost), 2))
        for cp in opt.selected_products:
            if cp.price is not None:
                amounts.add(round(float(cp.price), 2))
    for cat_response in (request.retrieval_by_category or {}).values():
        for res in (cat_response.results or []):
            if res.price is not None:
                amounts.add(round(float(res.price), 2))
    for piece in outfit_pieces:
        if getattr(piece, "price_usd", None) is not None:
            amounts.add(round(abs(float(piece.price_usd)), 2))
    for a in totals:
        for b in totals:
            amounts.add(round(abs(a - b), 2))
    return amounts


def _names_in_data(request: DecisionRequest, evaluated_pieces: Sequence) -> Set[str]:
    names: Set[str] = set()
    for opt in request.budget_response.options:
        names.add(opt.name)
        for cp in opt.selected_products:
            names.add(cp.name)
        for w in opt.wardrobe_items_used:
            names.add(f"{w.colour} {w.type}".strip())
    for cat_response in (request.retrieval_by_category or {}).values():
        for res in (cat_response.results or []):
            names.add(res.name)
    for w in request.agent1_output.wardrobe:
        names.add(f"{w.colour} {w.type}".strip())
    for piece in evaluated_pieces:
        names.add(getattr(piece, "name", "") or "")
    return {n.strip().lower() for n in names if n and n.strip()}


def _colours_in_data(request: DecisionRequest, chosen_pieces: Sequence, fallback_pieces: Sequence) -> Set[str]:
    ur = request.agent1_output.user_requirements
    colours = {c.lower() for c in ur.colour_preferences if c}
    colours |= {c.lower() for c in ur.excluded_colours if c}
    colours |= {it.colour.lower() for it in ur.identified_items if it.colour}
    colours |= {w.colour.lower() for w in request.agent1_output.wardrobe if w.colour}
    pieces = chosen_pieces if len(chosen_pieces) else fallback_pieces
    colours |= {(getattr(p, "colour", "") or "").lower() for p in pieces}
    colours |= {(getattr(p, "name", "") or "").lower() for p in pieces}
    return {c for c in colours if c}


def _stores_in_data(request: DecisionRequest) -> Set[str]:
    stores = set()
    for opt in request.budget_response.options:
        for cp in opt.selected_products:
            if cp.store:
                stores.add(cp.store.lower())
    for cat_response in (request.retrieval_by_category or {}).values():
        for res in (cat_response.results or []):
            if res.store:
                stores.add(res.store.lower())
    return stores


def _ids_in_data(request: DecisionRequest) -> Set[str]:
    ids = set()
    for opt in request.budget_response.options:
        ids.add(opt.combination_id)
        for cp in opt.selected_products:
            ids.add(cp.product_id)
        for w in opt.wardrobe_items_used:
            ids.add(w.wardrobe_id)
    for cat_response in (request.retrieval_by_category or {}).values():
        for res in (cat_response.results or []):
            ids.add(res.product_id)
    return ids


def _extracted_amounts(text: str) -> List[float]:
    out = []
    for raw in _AMOUNT_RE.findall(text or ""):
        try:
            out.append(round(float(raw.replace(",", "")), 2))
        except ValueError:
            continue
    return out


def _mentions_colour(text: str) -> List[str]:
    low = f" {(text or '').lower()} "
    return [c for c in _COLOUR_WORDS if re.search(rf"\b{re.escape(c)}\b", low)]


def _known_name(fragment: str, known: Iterable[str]) -> bool:
    for name in known:
        if fragment in name or name in fragment:
            return True
    return False


def verify(
    text: str,
    request: DecisionRequest,
    *,
    chosen_pieces: Sequence = (),
    all_pieces: Sequence = (),
) -> VerificationResult:
    """Check one explanation against the data it must be faithful to."""
    issues: List[str] = []
    body = text or ""

    allowed_amounts = _amounts_in_data(request, all_pieces)
    for amount in _extracted_amounts(body):
        if amount not in allowed_amounts:
            issues.append(f"amount_not_in_data: USD {_fmt(amount)}")

    # Arithmetic: a quoted "total … budget … leaving X" triple must add up.
    totals = [round(float(o.cost_breakdown.total_cost), 2)
              for o in request.budget_response.options]
    ceilings = [round(float(o.cost_breakdown.budget_ceiling), 2)
                for o in request.budget_response.options]
    for m in _LEAVING_RE.finditer(body):
        try:
            remaining = round(float(m.group(1).replace(",", "")), 2)
        except ValueError:
            continue
        prefix = body[max(0, m.start() - 220): m.start()]
        mentioned = _extracted_amounts(prefix)
        ok = any(
            abs(remaining - (ceiling - total)) <= settings.PRICE_CONSISTENCY_TOLERANCE_USD
            for total in mentioned
            for ceiling in ceilings
            if total in totals
        )
        if not ok:
            issues.append(f"arithmetic_mismatch: USD {_fmt(remaining)} left does not match the quoted total and budget")

    known_names = _names_in_data(request, all_pieces)
    known_blob = " ".join(known_names).upper()
    known_text = " ".join(known_names)
    for quoted in _QUOTED_RE.findall(body):
        fragment = quoted.strip().lower()
        if fragment and not _known_name(fragment, known_names):
            issues.append(f"name_not_in_data: {_clip(quoted)}")

    allowed_colours = _colours_in_data(request, chosen_pieces, all_pieces)
    for colour in _mentions_colour(body):
        if not any(colour in c or c in colour for c in allowed_colours):
            issues.append(f"colour_not_in_data: {colour}")

    low = body.lower()
    for term in _FORBIDDEN_TERMS:
        if term in low:
            issues.append(f"unverifiable_claim: {_clip(term)}")

    stores = _stores_in_data(request)
    for retailer in _WATCHED_RETAILERS:
        if (
            re.search(rf"\b{re.escape(retailer)}\b", low)
            and retailer not in stores
            and retailer not in known_text
        ):
            issues.append(f"store_not_in_data: {_clip(retailer)}")

    known_ids = _ids_in_data(request)
    for token in _ID_RE.findall(body):
        if token not in known_ids and token not in known_blob:
            issues.append(f"identifier_not_in_data: {_clip(token)}")

    unique = list(dict.fromkeys(issues))
    return VerificationResult(
        verified=not unique, issues=unique[: settings.MAX_VERIFICATION_ISSUES]
    )
