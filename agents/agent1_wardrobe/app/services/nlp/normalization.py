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

    # Remove item-specific colours that are bound to a particular garment
    # e.g. "black heel" → "black" belongs to "heel", not a general preference
    item_bound_colours = extract_item_specific_colours(text)
    preferences = [c for c in preferences if c not in item_bound_colours]

    return preferences, exclusions


def _parse_amount(num_str: str) -> Optional[float]:
    try:
        return float(num_str.replace(",", ""))
    except ValueError:
        return None


def extract_budget(text: str) -> Optional[float]:
    """Extracts budget ceiling; preserves None if unmentioned.

    Team convention (2026-09-25): budgets are USD, so small amounts like
    "under 50" are valid. The old LKR-era 100 floor only applied keyword
    matches without an explicit currency token.
    """
    lower = text.lower()

    # Superseded LKR-era pattern (narrow keywords, hard 100 floor):
    # r"(?:budget(?: of)?|spend(?: around)?|cost(?: of)?|under|around)\s*(?:lkr|rs\.?|\$)?\s*([0-9,]+)"

    currency = r"(?:lkr|rs\.?|usd|dollars?|bucks|rupees)"
    number = r"([0-9,]+(?:\.[0-9]+)?)"

    # Currency-keyword phrases: "budget of 50", "under $40", "up to 30 usd",
    # "no more than 100 dollars", "max 25", "within 80"
    for m in re.finditer(
        rf"(?:budget(?:\s+of)?|spend(?:\s+around)?|cost(?:\s+of)?|under|below|within|around|"
        rf"max(?:imum)?(?:\s+of)?|at\s+most|up\s+to|upto|less\s+than|no\s+more\s+than|"
        rf"not\s+more\s+than|capped\s+at)\s*(\$\s*)?{number}\s*({currency})?",
        lower,
    ):
        val = _parse_amount(m.group(2))
        if val is None:
            continue
        explicit_currency = bool(m.group(3)) or bool(m.group(1))
        if explicit_currency and 1 <= val <= 1_000_000:
            return val
        if not explicit_currency and 10 <= val <= 1_000_000:
            return val

    # Currency-adjacent amounts: "$50", "USD 50", "50 dollars", "Rs. 3000"
    for m in re.finditer(rf"(?:lkr|rs\.?|\$|usd)\s*{number}", lower):
        val = _parse_amount(m.group(1))
        if val is not None and 1 <= val <= 1_000_000:
            return val

    for m in re.finditer(rf"{number}\s*(?:{currency})", lower):
        val = _parse_amount(m.group(1))
        if val is not None and 1 <= val <= 1_000_000:
            return val

    return None


# Category labels must NOT appear in the types list — they are too generic for product search
_CATEGORY_LABEL_WORDS = {
    "top", "bottom", "dress", "footwear", "footwear",
    "bag", "accessory", "accessories", "outerwear",
}


def extract_requested_garments(text: str) -> Tuple[List[str], List[str]]:
    """
    Detects explicitly requested garment types/categories from text.
    Returns (categories, types) where:
      - categories: standardized category labels (top, bottom, dress, footwear, ...)
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


# ---------------------------------------------------------------------------
# Item-Role Extraction: existing vs requested
# ---------------------------------------------------------------------------

# Phrases that indicate OWNERSHIP (the user already has the item)
_OWNERSHIP_PATTERNS = [
    r"i have\b",
    r"i own\b",
    r"i've got\b",
    r"i got\b",
    r"i already have\b",
    r"already have\b",
    r"i'?m wearing\b",
    r"i am wearing\b",
    r"currently wearing\b",
    r"from my wardrobe\b",
    r"in my wardrobe\b",
]

# Phrases that indicate a REQUEST (the user wants to find/buy the item)
_REQUEST_PATTERNS = [
    r"i need\b",
    r"i want\b",
    r"i'?m looking for\b",
    r"looking for\b",
    r"find me\b",
    r"find\b",
    r"suggest\b",
    r"recommend\b",
    r"get me\b",
    r"something like\b",
    r"i'?d like\b",
    r"can you find\b",
    r"need\b",
    r"want\b",
]


def _build_garment_lookup() -> List[Tuple[str, str, str]]:
    """Returns [(synonym, category, canonical_type), ...] sorted by length desc."""
    garments = load_ontology().get("garments", {})
    ranked: List[Tuple[str, str, str]] = []
    for key, meta in garments.items():
        category = meta["category"]
        for syn in meta.get("synonyms", []):
            ranked.append((syn, category, key))
    ranked.sort(key=lambda x: len(x[0]), reverse=True)
    return ranked


def _find_garment_at(text: str, garment_lookup: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    """Find all garment mentions in a text fragment with their positions."""
    lower = text.lower()
    found: List[Dict[str, Any]] = []
    consumed_spans: List[Tuple[int, int]] = []

    for syn, category, canonical_type in garment_lookup:
        for m in re.finditer(r"\b" + re.escape(syn) + r"\b", lower):
            start, end = m.start(), m.end()
            # Check if this span overlaps with an already-consumed span
            overlaps = any(s <= start < e or s < end <= e for s, e in consumed_spans)
            if overlaps:
                continue
            consumed_spans.append((start, end))
            norm_type = syn.replace(" ", "_").replace("-", "_")
            if norm_type in _CATEGORY_LABEL_WORDS:
                norm_type = None  # bare category label, not a specific type
            found.append({
                "category": category,
                "type": norm_type,
                "position": start,
                "end": end,
            })

    found.sort(key=lambda x: x["position"])
    return found


def _find_colour_at(text: str) -> List[Dict[str, Any]]:
    """Find all colour mentions in a text fragment with their positions."""
    lower = text.lower()
    color_families = load_ontology().get("colours", {})
    found: List[Dict[str, Any]] = []

    for canonical, terms in color_families.items():
        for t in terms:
            for m in re.finditer(r"\b" + re.escape(t) + r"\b", lower):
                found.append({
                    "canonical": canonical,
                    "position": m.start(),
                    "end": m.end(),
                })

    found.sort(key=lambda x: x["position"])
    return found


def _associate_colours_to_items(
    colour_mentions: List[Dict[str, Any]],
    garment_mentions: List[Dict[str, Any]],
) -> Dict[int, str]:
    """
    Associates each colour with its nearest following garment noun.
    Returns {garment_index: colour_canonical}.
    E.g. "black heel" → colour "black" is associated with the heel garment.
    """
    associations: Dict[int, str] = {}
    for colour in colour_mentions:
        col_end = colour["end"]
        # Find the closest garment AFTER this colour (within ~30 chars)
        best_idx = None
        best_dist = 9999
        for i, garm in enumerate(garment_mentions):
            dist = garm["position"] - col_end
            if 0 <= dist < 30 and dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None:
            associations[best_idx] = colour["canonical"]
    return associations


def extract_items_with_roles(text: str) -> List[Dict[str, Any]]:
    """
    Extracts clothing items from text with their role (existing/requested)
    and item-specific colours.

    Returns list of dicts:
    [
        {"category": "footwear", "type": "heel", "colour": "black", "role": "requested"},
        {"category": "top", "type": "blouse", "colour": null, "role": "existing_reference"},
        ...
    ]
    """
    lower = text.lower()
    garment_lookup = _build_garment_lookup()

    # Strategy: split text into clauses by commas, "and", periods, semicolons
    # Then determine the role of each clause based on ownership/request signals
    clauses = re.split(r"[,;.]|\band\b", lower)

    # Track which role context is active
    # If the sentence starts without any ownership/request signal, default to "requested"
    items: List[Dict[str, Any]] = []
    current_role = "requested"  # default

    # But first, detect if there's an ownership vs request boundary in the full text
    has_ownership = any(re.search(pat, lower) for pat in _OWNERSHIP_PATTERNS)
    has_request = any(re.search(pat, lower) for pat in _REQUEST_PATTERNS)

    if has_ownership and has_request:
        # Mixed sentence: need to determine role per-clause
        # Find the position of ownership and request signals
        ownership_ranges: List[Tuple[int, int]] = []
        request_ranges: List[Tuple[int, int]] = []

        for pat in _OWNERSHIP_PATTERNS:
            for m in re.finditer(pat, lower):
                ownership_ranges.append((m.start(), m.end()))
        for pat in _REQUEST_PATTERNS:
            for m in re.finditer(pat, lower):
                request_ranges.append((m.start(), m.end()))

        # Find garments and colours in the full text
        all_garments = _find_garment_at(lower, garment_lookup)
        all_colours = _find_colour_at(lower)
        colour_assoc = _associate_colours_to_items(all_colours, all_garments)

        for i, garm in enumerate(all_garments):
            pos = garm["position"]
            # Determine role: find the nearest ownership or request signal BEFORE this garment
            role = "requested"  # default
            best_signal_pos = -1

            for (s, e) in ownership_ranges:
                if s < pos and s > best_signal_pos:
                    best_signal_pos = s
                    role = "existing_reference"
            for (s, e) in request_ranges:
                if s < pos and s > best_signal_pos:
                    best_signal_pos = s
                    role = "requested"

            item_colour = colour_assoc.get(i)
            items.append({
                "category": garm["category"],
                "type": garm["type"],
                "colour": item_colour,
                "role": role,
            })

    elif has_ownership and not has_request:
        # Pure ownership sentence — all items are existing
        all_garments = _find_garment_at(lower, garment_lookup)
        all_colours = _find_colour_at(lower)
        colour_assoc = _associate_colours_to_items(all_colours, all_garments)
        for i, garm in enumerate(all_garments):
            items.append({
                "category": garm["category"],
                "type": garm["type"],
                "colour": colour_assoc.get(i),
                "role": "existing_reference",
            })

    else:
        # No ownership signals — all items are requested (backward compatible)
        all_garments = _find_garment_at(lower, garment_lookup)
        all_colours = _find_colour_at(lower)
        colour_assoc = _associate_colours_to_items(all_colours, all_garments)
        for i, garm in enumerate(all_garments):
            items.append({
                "category": garm["category"],
                "type": garm["type"],
                "colour": colour_assoc.get(i),
                "role": "requested",
            })

    return items


def extract_item_specific_colours(text: str) -> set:
    """
    Returns the set of canonical colour names that are bound to a specific
    clothing item (e.g. 'black' in 'black heel') and should NOT be added
    to global colour_preferences.
    """
    items = extract_items_with_roles(text)
    return {item["colour"] for item in items if item.get("colour")}


# ---------------------------------------------------------------------------
# Garbled-word handling: conservative typo correction + unrecognized terms
# ---------------------------------------------------------------------------

# Common function words / fashion-domain words that are NOT garment nouns.
# They must never be reported as unrecognized.
_REQUEST_STOPWORDS = {
    # articles / prepositions / pronouns
    "a", "an", "the", "for", "to", "of", "in", "on", "with", "without", "and",
    "or", "my", "me", "i", "you", "your", "it", "that", "this", "some", "any",
    "something", "anything", "like", "as", "but", "not", "too", "very", "more",
    # request verbs / phrases
    "need", "needs", "wanted", "want", "looking", "find", "buy", "get", "suggest",
    "recommend", "search", "show", "help", "please", "can", "could", "would",
    # generic (non-garment) nouns and modifiers
    "outfit", "outfits", "clothes", "clothing", "wear", "wardrobe", "style",
    "styles", "look", "looks", "new", "nice", "good", "best", "right", "perfect",
    "occasion", "event", "budget", "spend", "money", "price", "cheap", "affordable",
    "under", "below", "within", "around", "maximum", "max", "least", "total",
    "rupees", "dollars", "lkr", "usd", "rs", "bucks",
    # everyday words that often sit in the request slot
    "dressy", "going", "weekend", "day", "night", "morning", "evening", "tomorrow",
    "next", "this_week", "really", "just", "also", "maybe", "probably", "again",
    "gym", "office", "college", "school", "university", "beach", "holiday", "trip",
    "party", "dinner", "lunch", "brunch", "date", "function", "ceremony", "reception",
    "interview", "meeting", "work", "wedding", "birthday", "concert", "club",
}

# Generic tail words: "a nice dress" — never flagged, never corrected.
_SLOT_GENERIC_WORDS = {"one", "thing", "piece", "item", "items", "number"}


def _edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (transpositions count as one edit)."""
    if a == b:
        return 0
    prev2: Optional[List[int]] = None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            val = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                val = min(val, prev2[j - 2] + cost)
            cur.append(val)
        prev2, prev = prev, cur
    return prev[len(b)]


def _max_typo_distance(word_len: int) -> int:
    # Conservative: only 1 edit for normal words, 2 for long ones, none for very short.
    if word_len <= 3:
        return 0
    return 1 if word_len <= 7 else 2


@lru_cache(maxsize=1)
def _garment_word_lexicon() -> Dict[str, str]:
    """token -> canonical correction target. Garment synonyms plus common colour words."""
    lexicon: Dict[str, str] = {}
    for meta in load_ontology().get("garments", {}).values():
        for syn in meta.get("synonyms", []):
            for token in re.findall(r"[a-z]+(?:-[a-z]+)*", syn.lower()):
                lexicon.setdefault(token, token)
    for canonical in load_ontology().get("colours", {}):
        lexicon.setdefault(canonical.lower(), canonical.lower())
    for syns in load_ontology().get("patterns", {}).values():
        for syn in syns:
            for token in re.findall(r"[a-z]+(?:-[a-z]+)*", syn.lower()):
                lexicon.setdefault(token, token)
    extra_colours = {
        "white", "black", "red", "blue", "green", "yellow", "pink", "purple",
        "orange", "brown", "grey", "gray", "navy", "beige", "cream", "maroon",
        "gold", "silver", "mint", "lavender", "turquoise", "teal", "burgundy",
    }
    for c in extra_colours:
        lexicon.setdefault(c, c)
    # common plurals of single-token garment words so "dresses" is known
    for token in list(lexicon.keys()):
        lexicon.setdefault(token + "s", token + "s")
        lexicon.setdefault(token + "es", token + "es")
    return lexicon


@lru_cache(maxsize=1)
def _known_vocabulary() -> set:
    """Every word the ontology understands: garments, colours, occasions, styles, patterns."""
    onto = load_ontology()
    known: set = set(_garment_word_lexicon().keys())
    for group in ("occasions", "styles", "colours", "patterns", "type_groups"):
        data = onto.get(group, {})
        for canonical, synonyms in data.items():
            known.add(canonical.lower().replace("_", " "))
            terms = synonyms if isinstance(synonyms, list) else synonyms.get("synonyms", [])
            for syn in terms:
                for token in re.findall(r"[a-z]+(?:-[a-z]+)*", str(syn).lower()):
                    known.add(token)
    return known


def _candidate_slots(lower: str) -> List[str]:
    """Word lists following request phrases and following articles."""
    slots: List[str] = []
    for pat, n in (
        (r"(?:i\s+need|i\s+want|i\s+would\s+like|i'?d\s+like|i'?m\s+looking\s+for|looking\s+for"
          r"|find\s+me|can\s+you\s+find|get\s+me|need\s+(?:a|an|some|to\s+buy)|want\s+(?:a|an|some)"
          r"|buy\s+(?:a|an|some|me)|search\s+for|suggest(?:\s+me)?|recommend(?:\s+me)?)", 6),
        (r"\b(?:a|an|the)\b", 4),
    ):
        for m in re.finditer(pat, lower):
            tail = lower[m.end():]
            words = re.findall(r"[a-z]+(?:-[a-z]+)*", tail[:80])
            slots.append(words[:n])
    return [s for s in slots if s]


def correct_garbled_words(text: str) -> Tuple[str, Dict[str, str], List[str]]:
    """
    Inside request slots ('i need a ...', 'a <word>'), match each word against the
    known fashion vocabulary. Unknown words within a conservative edit distance of
    a known garment/colour word are corrected (dres -> dress, whte -> white).
    Words that sit in a garment-noun position (directly after an article, or the
    tail word of the slot) with no close match are reported as unrecognized.
    Generic words (outfit, one, ...) and known vocabulary are never flagged.

    Returns (corrected_text, {original: corrected}, [unrecognized_terms]).
    """
    lower = text.lower()
    lexicon = _garment_word_lexicon()
    known = _known_vocabulary()
    corrections: Dict[str, str] = {}
    unrecognized: List[str] = []

    for words in _candidate_slots(lower):
        for i, w in enumerate(words):
            if w in lexicon or w in known or w in _REQUEST_STOPWORDS:
                continue
            best = None
            best_dist = 99
            limit = _max_typo_distance(len(w))
            if limit > 0:
                for kw in lexicon:
                    d = _edit_distance(w, kw)
                    if d < best_dist or (d == best_dist and best is not None and len(kw) < len(best)):
                        if d <= limit:
                            best, best_dist = kw, d
            if best is not None:
                corrections[w] = best
                continue
            prev_word = words[i - 1] if i > 0 else None
            is_noun_position = (i == len(words) - 1) or (prev_word in {"a", "an", "the"})
            looks_like_word = re.fullmatch(r"[a-z]{3,}", w) is not None
            if is_noun_position and looks_like_word and w not in _SLOT_GENERIC_WORDS:
                if w not in unrecognized:
                    unrecognized.append(w)

    if not corrections:
        return text, corrections, unrecognized

    corrected = text
    for orig, repl in corrections.items():
        corrected = re.sub(r"\b" + re.escape(orig) + r"\b", repl, corrected)
    return corrected, corrections, unrecognized
