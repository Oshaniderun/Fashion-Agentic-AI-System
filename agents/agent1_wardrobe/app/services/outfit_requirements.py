"""
Outfit Requirement Rules Engine.
Determines required and optional clothing categories based on occasion and style parameters.
"""

from typing import List, Dict, Tuple, Optional
from shared.schemas.agent1_schemas import UserRequirements, OutfitRequirements

# Configurable requirement templates by occasion
OCCASION_REQUIREMENT_RULES: Dict[str, Dict[str, List[str]]] = {
    "engagement": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag", "accessory"]
    },
    "wedding": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag", "accessory", "jewelry"]
    },
    "formal_event": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["outerwear", "bag", "accessory"]
    },
    "work": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag", "outerwear"]
    },
    "interview": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["outerwear", "bag"]
    },
    "dinner": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag", "accessory"]
    },
    "university": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag"]
    },
    "party": {
        "required": ["top", "bottom", "shoes"],
        "optional": ["bag", "accessory"]
    },
    "casual": {
        "required": ["top", "bottom"],
        "optional": ["shoes", "accessory"]
    }
}

DEFAULT_REQUIREMENTS = {
    "required": ["top", "bottom", "shoes"],
    "optional": ["accessory", "bag"]
}


class OutfitRequirementEngine:
    """Configurable outfit category requirement engine."""

    def determine_requirements(self, user_reqs: UserRequirements) -> Tuple[List[str], List[str]]:
        """
        Determines the list of required categories and optional categories
        based on the user's occasion and desired style.
        """
        occasion = (user_reqs.occasion or "").lower()

        rule = OCCASION_REQUIREMENT_RULES.get(occasion, DEFAULT_REQUIREMENTS)
        required = list(rule["required"])
        optional = list(rule["optional"])

        # Style-based adjustments: if formal or elegant, ensure shoes are required
        if any(s in ["formal", "semi_formal", "elegant"] for s in user_reqs.style):
            if "shoes" not in required:
                required.append("shoes")

        return required, optional


outfit_requirement_engine = OutfitRequirementEngine()
