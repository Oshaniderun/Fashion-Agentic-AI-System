"""
NLP Synonym Normalization and Ontology Mapping.
Loads editable synonym tables from app/config/nlp_ontology.json.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any


ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "config" / "nlp_ontology.json"


@lru_cache(maxsize=1)
def load_ontology() -> Dict[str, Any]:
    with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_occasion(text: str) -> Optional[str]:
    """Identifies and normalizes occasion from free text; preserves None if absent."""
    lower = text.lower()
    occasions = load_ontology().get("occasions", {})
    for canonical, synonyms in occasions.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", lower):
                return canonical
    return None


def normalize_styles(text: str) -> List[str]:
    """Identifies and normalizes style preferences from free text.
    More-specific styles suppress bare overlap (e.g. smart_casual suppresses casual).
    """
    lower = text.lower()
    detected_styles: List[str] = []
    styles = load_ontology().get("styles", {})

    if "not too formal" in lower or "not overly formal" in lower:
        detected_styles.append("semi_formal")

    for canonical, synonyms in styles.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", lower):
                if canonical == "formal" and ("not too formal" in lower or "not overly formal" in lower):
                    continue
                if canonical not in detected_styles:
                    detected_styles.append(canonical)

    # Post-process: if smart_casual was detected, remove bare 'casual'
    # (smart_casual already implies a refined casual — having both is redundant and misleading)
    if "smart_casual" in detected_styles and "casual" in detected_styles:
        detected_styles.remove("casual")

    return detected_styles


# Colour preference context phrases — only extract colours when in a preference context
_COLOUR_PREFERENCE_PREFIXES = [
    r"(?:prefer|want|like|love|need|looking for|something|wear|in)\s+",
    r"(?:colour|color)(?:s)?\s+(?:like|such as|including)?\s*",
]

# Negation phrases for colour exclusion
_COLOUR_NEGATION_PATTERNS = [
    r"(?:don'?t want|do not want|no|avoid|nothing|without|not wear|dislike|hate|not)\s+([a-z][a-z\s]{1,25}?)(?:\s+colours?|\s+colors?|\.|,|\s+and\s|\s+i\s|\s+can\s|$)",
    r"(?:not\s+(?:too\s+)?|nothing\s+)([a-z][a-z\s]{0,15}?)(?:\s+colours?|\s+colors?)",
]


def extract_color_preferences_and_exclusions(text: str) -> Tuple[List[str], List[str]]:
    """
    Extracts ONLY explicitly stated colour preferences and exclusions.
    Does NOT infer preferences from negations (e.g. excluding 'bright' does NOT imply preferring 'dark').
    """
    lower = text.lower()
    preferences: List[str] = []
    exclusions: List[str] = []
    color_families = load_ontology().get("colours", {})

    # Step 1: collect negated colour chunks
    negated_chunks: List[str] = []
    for pat in _COLOUR_NEGATION_PATTERNS:
        for m in re.finditer(pat, lower):
            chunk = m.group(1).strip()
            if chunk:
                negated_chunks.append(chunk)

    # Step 2: map negated chunks → colour exclusions
    for chunk in negated_chunks:
        for canonical, terms in color_families.items():
            for t in terms:
                if re.search(r"\b" + re.escape(t) + r"\b", chunk):
                    if canonical not in exclusions:
                        exclusions.append(canonical)

    # Step 3: extract positive preferences ONLY from preference-context phrases.
    # Colours mentioned in ownership context ("I have a red blouse") are NOT preferences.
    preference_context_text = lower
    # Remove ownership phrases so "I have a red blouse" doesn't produce colour preference = red
    ownership_phrases = re.sub(
        r"(?:i have|i own|i've got|i got|my|wearing|currently wearing|already have)\s+[^,.;]+",
        " ",
        lower,
    )
    preference_context_text = ownership_phrases

    for canonical, terms in color_families.items():
        if canonical in exclusions:
            continue
        for t in terms:
            if re.search(r"\b" + re.escape(t) + r"\b", preference_context_text):
                is_negated = any(
                    re.search(r"\b" + re.escape(t) + r"\b", chunk)
                    for chunk in negated_chunks
                )
                if not is_negated and canonical not in preferences:
                    preferences.append(canonical)

    # IMPORTANT: Do NOT auto-infer preferences from exclusions.
    # If user says "no bright colours" that is an exclusion, not a preference for dark/neutral.
    # Agent 2 will handle interpretation of excluded colours.

    return preferences, exclusions


def extract_budget(text: str) -> Optional[float]:
    """Extracts budget ceiling; preserves None if unmentioned."""
    lower = text.lower()

    budget_matches = re.finditer(
        r"(?:budget(?: of)?|spend(?: around)?|cost(?: of)?|under|around)\s*(?:lkr|rs\.?|\$)?\s*([0-9,]+)",
        lower,
    )
    for m in budget_matches:
        num_str = m.group(1).replace(",", "")
        try:
            val = float(num_str)
            if 100 <= val <= 1000000:
                return val
        except ValueError:
            continue

    for m in re.finditer(r"(?:lkr|rs\.?)\s*([0-9,]+)", lower):
        num_str = m.group(1).replace(",", "")
        try:
            val = float(num_str)
            if 100 <= val <= 1000000:
                return val
        except ValueError:
            continue

    return None


# Category labels must NOT appear in the types list — they are too generic for product search
_CATEGORY_LABEL_WORDS = {
    "top", "bottom", "dress", "shoes", "footwear",
    "bag", "accessory", "accessories", "outerwear",
}


def extract_requested_garments(text: str) -> Tuple[List[str], List[str]]:
    """
    Detects explicitly requested garment types/categories from text.
    Returns (categories, types) where:
      - categories: standardized category labels (top, bottom, dress, shoes, ...)
      - types: specific garment words useful for product search (blouse, jeans, loafers, ...)
               NEVER contains bare category labels like 'bottom' or 'top'
    Example: "a blouse and bottom pant" -> categories=["top", "bottom"], types=["blouse", "pants"]
    """
    lower = text.lower()
    garments = load_ontology().get("garments", {})
    categories: List[str] = []
    types: List[str] = []

    # Sort by synonym length descending so longer/more-specific phrases match first
    ranked: List[Tuple[str, str, str]] = []
    for key, meta in garments.items():
        category = meta["category"]
        for syn in meta.get("synonyms", []):
            ranked.append((syn, category, key))
    ranked.sort(key=lambda x: len(x[0]), reverse=True)

    for syn, category, canonical_type in ranked:
        if re.search(r"\b" + re.escape(syn) + r"\b", lower):
            if category not in categories:
                categories.append(category)
            # Only add to types if it is a specific garment word, NOT a bare category label
            norm = syn.replace(" ", "_").replace("-", "_")
            if norm not in _CATEGORY_LABEL_WORDS and norm not in types:
                types.append(norm)

    return categories, types


def extract_pattern_preferences(text: str) -> List[str]:
    """Detects pattern words like checked / striped from free text."""
    lower = text.lower()
    patterns = load_ontology().get("patterns", {})
    found: List[str] = []
    ranked = sorted(patterns.items(), key=lambda kv: max((len(s) for s in kv[1]), default=0), reverse=True)
    for canonical, synonyms in ranked:
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", lower):
                if canonical not in found:
                    found.append(canonical)
                break
    return found
