"""
Generic wardrobe-item vs request constraint matching.
Rules and synonym tables come from nlp_ontology.json — no per-colour/type cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.services.nlp.normalization import load_ontology
from shared.schemas.agent1_schemas import RequestedItem, UserRequirements, WardrobeSummaryItem


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _colour_canonical(token: str) -> str:
    raw = _norm(token)
    if not raw:
        return ""
    colours = load_ontology().get("colours", {})
    for canonical, synonyms in colours.items():
        if raw == _norm(canonical):
            return canonical
        for syn in synonyms:
            if raw == _norm(syn) or raw == syn.lower().replace(" ", "_"):
                return canonical
    return raw


def _colours_compatible(requested: str, owned: str) -> bool:
    req = _colour_canonical(requested)
    own = _colour_canonical(owned)
    if not req or not own:
        return True
    if req == own:
        return True
    families = load_ontology().get("colour_families", {})
    members = {_norm(m) for m in families.get(req, [])}
    if members and (_norm(own) in members or own in families.get(req, [])):
        return True
    return False


def _type_group(token: str) -> str:
    raw = _norm(token)
    if not raw:
        return ""
    groups = load_ontology().get("type_groups", {})
    for canonical, aliases in groups.items():
        if raw == _norm(canonical):
            return canonical
        for alias in aliases:
            if raw == _norm(alias):
                return canonical
    return raw


def _types_compatible(requested: Optional[str], owned: Optional[str]) -> bool:
    if not requested:
        return True
    category_labels = set(load_ontology().get("garments", {}).keys())
    req = _norm(requested)
    if req in category_labels:
        return True
    if not owned:
        return False
    return _type_group(requested) == _type_group(owned)


def _style_compatible(requested_styles: List[str], owned_style: Optional[str]) -> bool:
    if not requested_styles:
        return True
    owned = _norm(owned_style)
    wanted = {_norm(s) for s in requested_styles}
    return owned in wanted


def _pattern_compatible(requested_patterns: List[str], owned_pattern: Optional[str]) -> bool:
    if not requested_patterns:
        return True
    owned = _norm(owned_pattern)
    wanted = {_norm(p) for p in requested_patterns}
    return owned in wanted


@dataclass
class CategoryConstraints:
    category: str
    types: List[str] = field(default_factory=list)
    colours: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    excluded_colours: List[str] = field(default_factory=list)
    enforce_style: bool = False


def constraints_for_category(requirements: UserRequirements, category: str) -> CategoryConstraints:
    cat = category.lower()
    identified = [
        item
        for item in (requirements.identified_items or [])
        if (item.role or "requested") == "requested" and (item.category or "").lower() == cat
    ]
    types = [item.type for item in identified if item.type]
    colours = [item.colour for item in identified if item.colour]
    if not colours:
        family_keys = {k.lower() for k in load_ontology().get("colour_families", {}).keys()}
        colours = [
            c
            for c in (requirements.colour_preferences or [])
            if _colour_canonical(c) not in family_keys
        ]
    return CategoryConstraints(
        category=cat,
        types=types,
        colours=colours,
        styles=list(requirements.style or []),
        patterns=list(requirements.pattern_preferences or []),
        excluded_colours=list(requirements.excluded_colours or []),
        enforce_style=bool(identified) and bool(requirements.style),
    )


def mismatch_reason(item: WardrobeSummaryItem, constraints: CategoryConstraints) -> Optional[str]:
    reasons = load_ontology().get("match_reasons", {})
    for exc in constraints.excluded_colours:
        if _colours_compatible(exc, item.colour):
            return reasons.get("excluded_colour", "excluded_colour")
    if constraints.types and not any(_types_compatible(t, item.type) for t in constraints.types):
        return reasons.get("type", "type_mismatch")
    if constraints.colours and not any(_colours_compatible(c, item.colour) for c in constraints.colours):
        return reasons.get("colour", "colour_mismatch")
    if not _pattern_compatible(constraints.patterns, item.pattern):
        return reasons.get("pattern", "pattern_mismatch")
    if constraints.enforce_style and not _style_compatible(constraints.styles, item.style):
        return reasons.get("style", "style_mismatch")
    return None


def item_satisfies(item: WardrobeSummaryItem, constraints: CategoryConstraints) -> bool:
    return mismatch_reason(item, constraints) is None


def split_matching(
    owned_items: List[WardrobeSummaryItem],
    requirements: UserRequirements,
    required_categories: List[str],
) -> Tuple[List[WardrobeSummaryItem], List[Tuple[WardrobeSummaryItem, str]]]:
    matching: List[WardrobeSummaryItem] = []
    non_matching: List[Tuple[WardrobeSummaryItem, str]] = []
    required = [c.lower() for c in required_categories]
    for item in owned_items:
        if item.category.lower() not in required:
            continue
        constraints = constraints_for_category(requirements, item.category)
        reason = mismatch_reason(item, constraints)
        if reason:
            non_matching.append((item, reason))
        else:
            matching.append(item)
    return matching, non_matching
