"""
Missing Clothing Item Detection & Agent 2 Handoff Builder.
Compares required categories against owned wardrobe using full request constraints
(category + type + colour + style + pattern), not category presence alone.
"""

from typing import List, Set, Tuple

from app.services.item_match import (
    constraints_for_category,
    item_satisfies,
    split_matching,
)
from app.services.nlp.normalization import load_ontology
from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    Agent2SearchRequirement,
    Agent2HandoffPayload,
    Agent2WardrobeStatus,
    Agent2AvailableItem,
    Agent2NonMatchingItem,
)


def _category_labels() -> Set[str]:
    return {key.lower() for key in load_ontology().get("garments", {}).keys()} | {
        "accessories",
        "shoes",
        "footwear",
    }


def _type_to_category(token: str) -> str:
    raw = (token or "").strip().lower().replace(" ", "_")
    garments = load_ontology().get("garments", {})
    for key, meta in garments.items():
        category = str(meta.get("category", key)).lower()
        if raw == key.lower() or raw == category:
            return category
        for syn in meta.get("synonyms", []):
            if raw == syn.lower().replace(" ", "_").replace("-", "_"):
                return category
    groups = load_ontology().get("type_groups", {})
    for canonical, aliases in groups.items():
        names = [canonical, *aliases]
        if raw in {n.lower().replace(" ", "_") for n in names}:
            for key, meta in garments.items():
                syns = [key, *meta.get("synonyms", [])]
                if canonical.lower().replace(" ", "_") in {s.lower().replace(" ", "_") for s in syns}:
                    return str(meta.get("category", key)).lower()
    return raw


class MissingItemDetector:
    """Identifies missing clothing relative to explicit request constraints."""

    def analyze_missing(
        self,
        required_categories: List[str],
        optional_categories: List[str],
        owned_items: List[WardrobeSummaryItem],
        user_requirements: UserRequirements,
        request_id: str = "REQ-000",
    ) -> Tuple[OutfitRequirements, Agent2SearchRequirement, Agent2HandoffPayload]:
        owned_categories = {item.category.lower() for item in owned_items}

        present: List[str] = []
        unsatisfied: List[str] = []

        for req_cat in required_categories:
            cat_lower = req_cat.lower()
            in_wardrobe = cat_lower in owned_categories
            if in_wardrobe:
                present.append(req_cat)
            constraints = constraints_for_category(user_requirements, req_cat)
            satisfied = any(
                item.category.lower() == cat_lower and item_satisfies(item, constraints)
                for item in owned_items
            )
            if not satisfied:
                unsatisfied.append(req_cat)

        outfit_reqs = OutfitRequirements(
            required_categories=required_categories,
            available_categories=present,
            missing_categories=unsatisfied,
            optional_categories=optional_categories,
        )

        matching_owned, non_matching_owned = split_matching(
            owned_items, user_requirements, required_categories
        )
        search_brief = self._build_search_brief(unsatisfied, user_requirements)
        available_items = [
            Agent2AvailableItem(
                wardrobe_id=item.wardrobe_id,
                category=item.category,
                type=item.type,
                colour=item.colour,
            )
            for item in owned_items
            if item.category.lower() in {c.lower() for c in present}
        ]

        handoff = Agent2HandoffPayload(
            request_id=request_id,
            user_requirements=user_requirements,
            wardrobe_status=Agent2WardrobeStatus(
                available_categories=list(present),
                missing_categories=list(unsatisfied),
                matching_items=[
                    Agent2AvailableItem(
                        wardrobe_id=item.wardrobe_id,
                        category=item.category,
                        type=item.type,
                        colour=item.colour,
                    )
                    for item in matching_owned
                ],
                non_matching_items=[
                    Agent2NonMatchingItem(
                        wardrobe_id=item.wardrobe_id,
                        category=item.category,
                        type=item.type,
                        colour=item.colour,
                        reason=reason,
                    )
                    for item, reason in non_matching_owned
                ],
            ),
            available_items=available_items,
            search_requirements=search_brief,
        )

        return outfit_reqs, search_brief, handoff

    def _build_search_brief(
        self,
        missing: List[str],
        user_requirements: UserRequirements,
    ) -> Agent2SearchRequirement:
        missing_norm = [c.lower() for c in missing]
        matching_refs = [
            item
            for item in (user_requirements.identified_items or [])
            if item.role == "existing_reference"
        ]

        if not missing_norm:
            return Agent2SearchRequirement(
                categories=[],
                missing_categories=[],
                types=[],
                style=[],
                colour_preferences=[],
                colour=[],
                pattern_preferences=[],
                pattern=[],
                occasion=user_requirements.occasion,
                maximum_price=user_requirements.budget,
                budget_remaining=user_requirements.budget,
                query_text=None,
                matching_reference_items=matching_refs,
            )

        search_types: List[str] = []
        search_colours: List[str] = []
        for cat in missing_norm:
            constraints = constraints_for_category(user_requirements, cat)
            for t in constraints.types:
                spaced = t.replace("_", " ")
                if spaced not in search_types and _norm_token(t) not in _category_labels():
                    search_types.append(spaced)
            for c in constraints.colours:
                if c not in search_colours:
                    search_colours.append(c)
        if not search_colours:
            search_colours = list(user_requirements.colour_preferences or [])

        styles = list(user_requirements.style or [])
        patterns = list(user_requirements.pattern_preferences or [])
        budget = user_requirements.budget
        query_text = self._build_query_text(
            missing=missing_norm,
            styles=styles,
            colours=search_colours,
            patterns=patterns,
            search_types=search_types,
            matching_refs=matching_refs,
            occasion=user_requirements.occasion,
            budget=budget,
        )

        return Agent2SearchRequirement(
            categories=list(missing_norm),
            missing_categories=list(missing_norm),
            types=search_types,
            style=styles,
            colour_preferences=search_colours,
            colour=search_colours,
            pattern_preferences=patterns,
            pattern=patterns,
            occasion=user_requirements.occasion,
            maximum_price=budget,
            budget_remaining=budget,
            query_text=query_text,
            matching_reference_items=matching_refs,
        )

    def _build_query_text(
        self,
        missing: List[str],
        styles: List[str],
        colours: List[str],
        patterns: List[str],
        search_types: List[str],
        matching_refs: list,
        occasion: str | None,
        budget: float | None,
    ) -> str:
        covered_cats = {_type_to_category(t) for t in search_types}
        cat_tokens = [c for c in missing if c not in covered_cats]

        parts: List[str] = []
        parts.extend(styles)
        parts.extend(colours)
        parts.extend(patterns)
        parts.extend(search_types)
        parts.extend(cat_tokens)
        if occasion:
            parts.append(f"for {occasion}")
        if matching_refs:
            ref_strs = []
            for ref in matching_refs:
                colour = ref.colour or ""
                kind = ref.type or ref.category
                ref_strs.append(f"{colour} {kind}".strip())
            parts.append(f"matching {' and '.join(ref_strs)}")
        if budget:
            parts.append(f"under LKR {int(budget)}")

        seen: Set[str] = set()
        out: List[str] = []
        for part in parts:
            for word in str(part).split():
                key = word.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(word)
        return " ".join(out).strip() or "fashion item"


def _norm_token(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


missing_item_detector = MissingItemDetector()
