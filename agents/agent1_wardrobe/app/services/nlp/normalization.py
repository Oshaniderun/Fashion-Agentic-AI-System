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
    """Identifies and normalizes style preferences from free text."""
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

    return detected_styles


def extract_color_preferences_and_exclusions(text: str) -> Tuple[List[str], List[str]]:
    """Extracts preferred colors and explicitly excluded colors."""
    lower = text.lower()
    preferences: List[str] = []
    exclusions: List[str] = []
    color_families = load_ontology().get("colours", {})

    negation_patterns = [
        r"(?:don't want|do not want|no|avoid|nothing|without|dislike)\s+([a-z\s]+?)(?:\.|,|and|\s+and|\s+i|\s+can|$)",
        r"(?:not)\s+([a-z\s]+?)(?:colours?|colors?)",
    ]

    negated_chunks: List[str] = []
    for pat in negation_patterns:
        for m in re.findall(pat, lower):
            negated_chunks.append(m.strip())

    for chunk in negated_chunks:
        for canonical, terms in color_families.items():
            for t in terms:
                if t in chunk and canonical not in exclusions:
                    exclusions.append(canonical)

    for canonical, terms in color_families.items():
        if canonical in exclusions:
            continue
        for t in terms:
            if re.search(r"\b" + re.escape(t) + r"\b", lower):
                is_negated = any(t in chunk for chunk in negated_chunks)
                if not is_negated and canonical not in preferences:
                    preferences.append(canonical)

    if "bright" in exclusions and not preferences:
        preferences.extend(["dark", "neutral"])

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


def extract_requested_garments(text: str) -> Tuple[List[str], List[str]]:
    """
    Detects explicitly requested garment types/categories from text.
    Example: "beige frock" -> categories=["dress"], types=["frock"]
    """
    lower = text.lower()
    garments = load_ontology().get("garments", {})
    categories: List[str] = []
    types: List[str] = []

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
            label = syn.replace(" ", "_")
            if label not in types:
                types.append(label)

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
