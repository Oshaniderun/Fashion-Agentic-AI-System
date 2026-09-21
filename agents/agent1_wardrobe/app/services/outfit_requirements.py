"""
Outfit Requirement Rules Engine.
Loads editable rules from app/config/outfit_rules.json.
Respects explicitly requested garments (e. nights frock/dress) over default full outfits.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Tuple, Any

from shared.schemas.agent1_schemas import UserRequirements


RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "outfit_rules.json"


@lru_cache(maxsize=1)
def load_outfit_rules() -> Dict[str, Any]:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class OutfitRequirementEngine:
    """Configurable outfit category requirement engine."""

    def determine_requirements(self, user_reqs: UserRequirements) -> Tuple[List[str], List[str]]:
        """
        Priority:
        1. Explicit garment requests in the user text (e.g. frock -> dress)
        2. Occasion-based full outfit template
        3. Default full outfit (only when no garment and no occasion)
        """
        rules = load_outfit_rules()
        requested = [c.lower() for c in (user_reqs.requested_categories or [])]

        if requested:
            required: List[str] = []
            optional: List[str] = []
            by_req = rules.get("by_requested_category", {})
            for cat in requested:
                tmpl = by_req.get(cat)
                if not tmpl:
                    # Unknown category: treat the category itself as required
                    if cat not in required:
                        required.append(cat)
                    continue
                for r in tmpl.get("required", []):
                    if r not in required:
                        required.append(r)
                for o in tmpl.get("optional", []):
                    if o not in optional and o not in required:
                        optional.append(o)

            # If user asked only for a dress/top/etc., do not force a full 3-piece outfit
            return required, optional

        occasion = (user_reqs.occasion or "").lower()
        by_occasion = rules.get("by_occasion", {})
        default = rules.get("default_full_outfit", {"required": ["top", "bottom", "shoes"], "optional": []})

        if occasion and occasion in by_occasion:
            rule = by_occasion[occasion]
        elif occasion:
            rule = default
        else:
            # No occasion and no explicit garment → keep a conservative full-outfit default
            rule = default

        required = list(rule.get("required", []))
        optional = list(rule.get("optional", []))

        shoe_styles = rules.get("styles_requiring_shoes", [])
        if any(s in shoe_styles for s in user_reqs.style):
            if "shoes" not in required:
                required.append("shoes")

        return required, optional


outfit_requirement_engine = OutfitRequirementEngine()
