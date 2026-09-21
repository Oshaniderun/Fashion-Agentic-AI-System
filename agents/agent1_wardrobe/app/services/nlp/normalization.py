"""
NLP Synonym Normalization and Ontology Mapping.
Normalizes colloquial terms, handles negation, and preserves uncertainty.
"""

import re
from typing import Optional, List, Tuple, Dict, Any

OCCASION_SYNONYMS = {
    "engagement": [
        "engagement", "cousin's engagement", "engagement party", "engagement dinner", "ring ceremony"
    ],
    "wedding": [
        "wedding", "wedding ceremony", "marriage", "reception", "nuptials", "bridal shower"
    ],
    "university": [
        "university", "college", "campus", "lecture", "presentation", "uni event"
    ],
    "interview": [
        "interview", "job interview", "hiring interview", "tech interview",
        "for an interview", "for a job interview", "corporate interview",
        "for my interview", "interview outfit"
    ],
    "work": [
        "work", "office", "meeting", "business", "client meeting"
    ],
    "dinner": [
        "dinner", "dinner date", "formal dinner", "restaurant", "gala dinner", "evening dinner"
    ],
    "party": [
        "party", "birthday party", "celebration", "night out", "clubbing"
    ],
    "casual": [
        "casual outing", "weekend outing", "hangout", "coffee", "brunch", "errands"
    ]
}

STYLE_SYNONYMS = {
    "semi_formal": [
        "semi-formal", "semi formal", "not too formal", "dressy casual", "smart evening"
    ],
    "elegant": [
        "elegant", "classy", "sophisticated", "chic", "refined", "graceful"
    ],
    "smart_casual": [
        "smart casual", "smart-casual", "business casual", "polished casual"
    ],
    "formal": [
        "formal", "black tie", "suit and tie", "strictly formal"
    ],
    "casual": [
        "casual", "laid back", "relaxed", "everyday", "comfortable"
    ],
    "streetwear": [
        "streetwear", "urban", "edgy", "oversized"
    ],
    "minimalist": [
        "minimalist", "minimal", "clean", "simple"
    ]
}

COLOR_FAMILIES = {
    "dark": ["dark", "deep", "black", "navy", "charcoal", "dark grey", "dark colours", "dark colors"],
    "neutral": ["neutral", "neutrals", "beige", "cream", "white", "grey", "gray", "brown", "tan", "nude", "neutral colours"],
    "bright": ["bright", "vibrant", "neon", "flashy", "loud", "bright colours", "bright colors"],
    "pastel": ["pastel", "soft", "light pink", "baby blue", "lavender", "mint"],
    "black": ["black"],
    "white": ["white"],
    "blue": ["blue", "navy blue", "royal blue"],
    "red": ["red", "crimson", "maroon", "burgundy"],
    "green": ["green", "olive", "emerald"],
    "yellow": ["yellow", "mustard"],
    "beige": ["beige", "camel", "khaki"],
    "brown": ["brown", "chocolate", "mocha"],
}


def normalize_occasion(text: str) -> Optional[str]:
    """Identifies and normalizes occasion from free text; preserves None if absent."""
    lower = text.lower()
    for canonical, synonyms in OCCASION_SYNONYMS.items():
        for syn in synonyms:
            # Word boundary matching
            if re.search(r"\b" + re.escape(syn) + r"\b", lower):
                return canonical
    return None


def normalize_styles(text: str) -> List[str]:
    """Identifies and normalizes style preferences from free text."""
    lower = text.lower()
    detected_styles: List[str] = []

    # Handle negative expressions like "not too formal" first
    if "not too formal" in lower or "not overly formal" in lower:
        detected_styles.append("semi_formal")

    for canonical, synonyms in STYLE_SYNONYMS.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", lower):
                # Don't add "formal" if "not too formal" was meant
                if canonical == "formal" and ("not too formal" in lower or "not overly formal" in lower):
                    continue
                if canonical not in detected_styles:
                    detected_styles.append(canonical)

    return detected_styles


def extract_color_preferences_and_exclusions(text: str) -> Tuple[List[str], List[str]]:
    """
    Extracts preferred colors and explicitly excluded colors (e.g. 'don't want bright colours').
    """
    lower = text.lower()
    preferences: List[str] = []
    exclusions: List[str] = []

    # Detect negation/exclusion patterns: "don't want X", "no X", "avoid X", "nothing X"
    negation_patterns = [
        r"(?:don't want|do not want|no|avoid|nothing|without|dislike)\s+([a-z\s]+?)(?:\.|,|and|\s+and|\s+i|\s+can|$)",
        r"(?:not)\s+([a-z\s]+?)(?:colours?|colors?)"
    ]

    negated_chunks = []
    for pat in negation_patterns:
        matches = re.findall(pat, lower)
        for m in matches:
            negated_chunks.append(m.strip())

    # Map negated chunks to colors
    for chunk in negated_chunks:
        for canonical, terms in COLOR_FAMILIES.items():
            for t in terms:
                if t in chunk and canonical not in exclusions:
                    exclusions.append(canonical)

    # Now detect positive color preferences
    for canonical, terms in COLOR_FAMILIES.items():
        if canonical in exclusions:
            continue
        for t in terms:
            if re.search(r"\b" + re.escape(t) + r"\b", lower):
                # Check if it was part of a negation sentence
                is_negated = any(t in chunk for chunk in negated_chunks)
                if not is_negated and canonical not in preferences:
                    preferences.append(canonical)

    # Special handling for "I don't want bright colours" -> if bright is excluded, user often implicitly prefers dark/neutral
    if "bright" in exclusions and not preferences:
        preferences.extend(["dark", "neutral"])

    return preferences, exclusions


def extract_budget(text: str) -> Optional[float]:
    """
    Extracts budget ceiling in numbers, preserving None if unmentioned.
    Handles 'around 8000', 'LKR 10,000', 'budget 7000', 'under 5000'.
    """
    lower = text.lower()
    # Match currency prefix/affix and numbers
    patterns = [
        r"(?:budget|spend|cost|around|under|max|maximum|ceiling|approx|approximately)?\s*(?:lkr|rs\.?|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,7})\s*(?:lkr|rs\.?|rupees)?",
    ]

    budget_matches = re.finditer(
        r"(?:budget(?: of)?|spend(?: around)?|cost(?: of)?|under|around)\s*(?:lkr|rs\.?|\$)?\s*([0-9,]+)",
        lower
    )
    for m in budget_matches:
        num_str = m.group(1).replace(",", "")
        try:
            val = float(num_str)
            if 100 <= val <= 1000000:
                return val
        except ValueError:
            continue

    # Standalone currency mention like 'LKR 8,000' or '8000 LKR'
    curr_matches = re.finditer(r"(?:lkr|rs\.?)\s*([0-9,]+)", lower)
    for m in curr_matches:
        num_str = m.group(1).replace(",", "")
        try:
            val = float(num_str)
            if 100 <= val <= 1000000:
                return val
        except ValueError:
            continue

    return None
