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
    "loafers": "footwear",
    "sneakers": "footwear",
    "boots": "footwear",
    "heels": "footwear",
    "sandals": "footwear",
    "slippers": "footwear",
    "flats": "footwear",
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
        missing_norm = [c.lower() for c in missing]

        # Extract matching_reference_items (always needed for context)
        matching_refs = []
        for item in user_requirements.identified_items:
            role = getattr(item, 'role', None) or (item.get('role') if isinstance(item, dict) else None)
            if role == "existing_reference":
                matching_refs.append(item)

        # If nothing is missing, Agent 2 has nothing to search for.
        # Return a minimal brief with only reference context.
        if not missing_norm:
            return Agent2SearchRequirement(
                categories=[],
                missing_categories=[],
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

        colours = list(user_requirements.colour_preferences or [])
        patterns = list(user_requirements.pattern_preferences or [])
        styles = list(user_requirements.style or [])
        budget = user_requirements.budget

        query_text = self._build_query_text(
            missing=missing_norm,
            styles=styles,
            global_colours=colours,
            patterns=patterns,
            identified_items=user_requirements.identified_items,
            matching_refs=matching_refs,
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
            matching_reference_items=matching_refs,
        )

    def _build_query_text(
        self,
        missing: List[str],
        styles: List[str],
        global_colours: List[str],
        patterns: List[str],
        identified_items: list,
        matching_refs: list,
        occasion: str | None,
        budget: float | None,
    ) -> str:
        """
        Build a deduped search query focused on *missing requested* categories only.
        Only includes item-specific colours for garments that are actually missing.
        """
        missing_set = set(missing)
        
        search_types: List[str] = []
        item_colours: List[str] = []

        # Find items that the user requested AND that are missing from wardrobe
        for item in identified_items:
            cat = getattr(item, 'category', None) or (item.get('category') if isinstance(item, dict) else None)
            role = getattr(item, 'role', None) or (item.get('role') if isinstance(item, dict) else None)
            t = getattr(item, 'type', None) or (item.get('type') if isinstance(item, dict) else None)
            c = getattr(item, 'colour', None) or (item.get('colour') if isinstance(item, dict) else None)
            
            if cat in missing_set and role == "requested":
                if t and t not in _CATEGORY_LABELS:
                    t_spaced = t.replace("_", " ")
                    if t_spaced not in search_types:
                        search_types.append(t_spaced)
                if c and c not in item_colours:
                    item_colours.append(c)

        # Category tokens only if no more specific type already covers them
        covered_cats = {
            _TYPE_TO_CATEGORY.get(t.replace(" ", "_"), t) for t in search_types
        }
        cat_tokens = [c for c in missing if c not in covered_cats]

        parts: List[str] = []
        parts.extend(styles)
        parts.extend(global_colours)
        parts.extend(item_colours)
        parts.extend(patterns)
        parts.extend(search_types)
        parts.extend(cat_tokens)
        
        if occasion:
            parts.append(f"for {occasion}")
            
        if matching_refs:
            ref_strs = []
            for ref in matching_refs:
                c = getattr(ref, 'colour', None) or (ref.get('colour') if isinstance(ref, dict) else None)
                t = getattr(ref, 'type', None) or (ref.get('type') if isinstance(ref, dict) else None)
                cat = getattr(ref, 'category', None) or (ref.get('category') if isinstance(ref, dict) else None)
                ref_str = f"{c + ' ' if c else ''}{t or cat}"
                ref_strs.append(ref_str)
            parts.append(f"matching {' and '.join(ref_strs)}")
            
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
