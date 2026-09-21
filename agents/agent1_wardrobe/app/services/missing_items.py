"""
Missing Clothing Item Detection & Agent 2 Handoff Builder.
Compares required categories against owned wardrobe inventory to detect gaps.
"""

from typing import List, Set, Tuple

from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    Agent2SearchRequirement,
    Agent2HandoffPayload,
    Agent2WardrobeStatus,
    Agent2AvailableItem,
)

# Words that are category labels, not specific garment types for search queries
_CATEGORY_LABELS = {
    "top",
    "bottom",
    "dress",
    "shoes",
    "footwear",
    "outerwear",
    "bag",
    "accessory",
    "accessories",
}

# Map specific types → category (for filtering search types to missing cats only)
_TYPE_TO_CATEGORY = {
    "blouse": "top",
    "shirt": "top",
    "t-shirt": "top",
    "tshirt": "top",
    "tee": "top",
    "sweater": "top",
    "tank_top": "top",
    "kurta": "top",
    "jeans": "bottom",
    "trousers": "bottom",
    "pants": "bottom",
    "skirt": "bottom",
    "shorts": "bottom",
    "leggings": "bottom",
    "palazzo": "bottom",
    "frock": "dress",
    "gown": "dress",
    "midi_dress": "dress",
    "maxi_dress": "dress",
    "loafers": "shoes",
    "sneakers": "shoes",
    "boots": "shoes",
    "heels": "shoes",
    "sandals": "shoes",
    "slippers": "shoes",
    "flats": "shoes",
    "blazer": "outerwear",
    "jacket": "outerwear",
    "coat": "outerwear",
    "handbag": "bag",
    "tote": "bag",
    "tote_bag": "bag",
    "clutch": "bag",
    "backpack": "bag",
    "purse": "bag",
    "belt": "accessory",
    "scarf": "accessory",
    "hat": "accessory",
    "jewelry": "accessory",
    "jewellery": "accessory",
}


class MissingItemDetector:
    """Identifies missing clothing categories to satisfy outfit requirements."""

    def analyze_missing(
        self,
        required_categories: List[str],
        optional_categories: List[str],
        owned_items: List[WardrobeSummaryItem],
        user_requirements: UserRequirements,
        request_id: str = "REQ-000",
    ) -> Tuple[OutfitRequirements, Agent2SearchRequirement, Agent2HandoffPayload]:
        """
        Determines available vs missing categories and structures the Agent 2 handoff.
        """
        owned_categories = {item.category.lower() for item in owned_items}

        available: List[str] = []
        missing: List[str] = []

        for req_cat in required_categories:
            cat_lower = req_cat.lower()
            if cat_lower in ["shoes", "footwear"]:
                if "shoes" in owned_categories or "footwear" in owned_categories:
                    available.append(req_cat)
                else:
                    missing.append(req_cat)
            else:
                if cat_lower in owned_categories:
                    available.append(req_cat)
                else:
                    missing.append(req_cat)

        outfit_reqs = OutfitRequirements(
            required_categories=required_categories,
            available_categories=available,
            missing_categories=missing,
            optional_categories=optional_categories,
        )

        search_brief = self._build_search_brief(missing, user_requirements)
        available_items = self._available_items_for_handoff(owned_items, available)

        handoff = Agent2HandoffPayload(
            request_id=request_id,
            user_requirements=user_requirements,
            wardrobe_status=Agent2WardrobeStatus(
                available_categories=list(available),
                missing_categories=list(missing),
            ),
            available_items=available_items,
            search_requirements=search_brief,
        )

        return outfit_reqs, search_brief, handoff

    def _available_items_for_handoff(
        self,
        owned_items: List[WardrobeSummaryItem],
        available_categories: List[str],
    ) -> List[Agent2AvailableItem]:
        avail = {c.lower() for c in available_categories}
        # Prefer one representative item per available category
        picked: List[Agent2AvailableItem] = []
        seen_cats: Set[str] = set()
        for item in owned_items:
            cat = item.category.lower()
            if cat not in avail or cat in seen_cats:
                continue
            seen_cats.add(cat)
            picked.append(
                Agent2AvailableItem(
                    wardrobe_id=item.wardrobe_id,
                    category=item.category,
                    type=item.type,
                    colour=item.colour,
                )
            )
        return picked

    def _build_search_brief(
        self,
        missing: List[str],
        user_requirements: UserRequirements,
    ) -> Agent2SearchRequirement:
        colours = list(user_requirements.colour_preferences or [])
        patterns = list(user_requirements.pattern_preferences or [])
        styles = list(user_requirements.style or [])
        budget = user_requirements.budget
        missing_norm = [c.lower() for c in missing]

        query_text = self._build_query_text(
            missing=missing_norm,
            styles=styles,
            colours=colours,
            patterns=patterns,
            requested_types=list(user_requirements.requested_types or []),
            occasion=user_requirements.occasion,
            budget=budget,
        )

        return Agent2SearchRequirement(
            categories=list(missing_norm),
            missing_categories=list(missing_norm),
            style=styles,
            colour_preferences=colours,
            colour=colours,
            pattern_preferences=patterns,
            pattern=patterns,
            occasion=user_requirements.occasion,
            maximum_price=budget,
            budget_remaining=budget,
            query_text=query_text,
        )

    def _build_query_text(
        self,
        missing: List[str],
        styles: List[str],
        colours: List[str],
        patterns: List[str],
        requested_types: List[str],
        occasion: str | None,
        budget: float | None,
    ) -> str:
        """
        Build a deduped search query focused on *missing* categories only.
        Avoids 'bottom bottom' when both requested_types and missing contain 'bottom'.
        """
        missing_set = set(missing)

        # Keep specific garment words that belong to a missing category
        search_types: List[str] = []
        for raw in requested_types:
            t = raw.strip().lower().replace(" ", "_")
            if not t or t in _CATEGORY_LABELS:
                continue
            mapped = _TYPE_TO_CATEGORY.get(t)
            if mapped and mapped not in missing_set:
                # User already owns this category — don't ask Agent 2 for it
                continue
            if mapped is None or mapped in missing_set:
                if t not in search_types:
                    search_types.append(t.replace("_", " "))

        # Category tokens only if no more specific type already covers them
        covered_cats = {
            _TYPE_TO_CATEGORY.get(t.replace(" ", "_"), t) for t in search_types
        }
        cat_tokens = [c for c in missing if c not in covered_cats]

        parts: List[str] = []
        parts.extend(styles)
        parts.extend(colours)
        parts.extend(patterns)
        parts.extend(search_types)
        parts.extend(cat_tokens)
        if occasion:
            parts.append(f"for {occasion}")
        if budget:
            parts.append(f"under LKR {int(budget)}")

        # Token-level dedupe while preserving order
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


missing_item_detector = MissingItemDetector()
