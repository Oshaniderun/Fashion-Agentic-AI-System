"""
Gemini Vision Clothing Analyzer.

Uses the configured Gemini multimodal LLM to accurately identify:
  - Category (top, bottom, shoes, outerwear, dress, bag, accessory)
  - Specific garment type (blouse, jeans, loafers, sandals, etc.)
  - Dominant colour + secondary colour
  - Pattern (solid, striped, floral, checked, etc.)
  - Inferred style/formality

This replaces the geometry-only heuristic fallback with a real vision model.
Supported backends: gemini | mock (tests)
Falls back to heuristic CLIP analyzer if LLM call fails.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Dict, Optional

from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.schemas.wardrobe import ClothingAttributesDetected


# ── Valid values (matches ontology + DB) ──────────────────────────────────────
_VALID_CATEGORIES = {"top", "bottom", "shoes", "outerwear", "dress", "bag", "accessory"}

_VALID_TYPES: Dict[str, list[str]] = {
    "top": ["blouse", "shirt", "t-shirt", "sweater", "tank_top", "crop_top", "hoodie", "kurta"],
    "bottom": ["jeans", "trousers", "skirt", "shorts", "leggings", "palazzo", "chinos"],
    "shoes": ["loafers", "sneakers", "boots", "heels", "sandals", "slippers", "flats", "formal_shoes"],
    "outerwear": ["blazer", "jacket", "coat", "cardigan", "trench_coat"],
    "dress": ["midi_dress", "maxi_dress", "cocktail_dress", "frock", "jumpsuit", "romper", "mini_dress"],
    "bag": ["handbag", "tote_bag", "clutch", "backpack", "purse"],
    "accessory": ["belt", "scarf", "hat", "jewelry", "necklace", "bracelet", "earrings",
                  "ring", "sunglasses", "watch", "tie", "shawl"],
}

_VALID_PATTERNS = {"solid", "striped", "checked", "floral", "printed", "polka_dot", "textured", "unknown"}
_VALID_COLOURS = {
    "black", "white", "grey", "blue", "red", "green", "yellow",
    "beige", "brown", "pink", "purple", "orange", "navy", "dark", "neutral", "bright", "pastel",
}

_GEMINI_PROMPT = """\
You are a clothing classification expert. Analyze this clothing/accessory image and return ONLY a valid JSON object.

Rules:
- category MUST be one of: top, bottom, shoes, outerwear, dress, bag, accessory
- type MUST be the most specific garment name you can identify
- colour MUST be the single dominant colour (e.g. "black", "red", "beige", "navy")
- secondary_colour is the second most prominent colour, or null if essentially one colour
- pattern MUST be one of: solid, striped, checked, floral, printed, polka_dot, textured, unknown
- formality is a float 0.0 (very casual) to 1.0 (very formal)
- style MUST be one of: casual, smart_casual, semi_formal, formal, elegant, streetwear, minimalist
- confidence is your confidence 0.0 to 1.0
- Do NOT make assumptions about who wears it. Focus only on visible attributes.
- If it's clearly footwear, category MUST be "shoes". If it's clearly a bag/purse, category MUST be "bag".

Return ONLY this JSON, no markdown, no explanation:
{
  "category": "...",
  "type": "...",
  "colour": "...",
  "secondary_colour": "...",
  "pattern": "...",
  "formality": 0.0,
  "style": "...",
  "sleeve_type": null,
  "material": null,
  "confidence": 0.0
}
"""


def _pil_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    """Encode PIL image to base64 string for Gemini API."""
    buf = io.BytesIO()
    rgb = image.convert("RGB")
    rgb.save(buf, format=fmt, quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _pil_to_base64_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    """Return PIL image as raw JPEG bytes."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format=fmt, quality=90)
    return buf.getvalue()


def _call_gemini_vision(image: Image.Image) -> Optional[Dict[str, Any]]:
    """
    Send image + prompt to Gemini Vision.
    Tries the configured model first, then fallback models, with up to 3 retries each.
    Returns parsed JSON dict, or None if all attempts fail.
    """
    import time
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    # Only confirmed-working free models (others return 404).
    # gemini-3.6-flash = primary; gemini-3.5-flash = secondary (may also be overloaded).
    # Both are free on Google AI Studio with no payment needed.
    models_to_try = [settings.LLM_MODEL]
    if settings.LLM_MODEL != "gemini-3.5-flash":
        models_to_try.append("gemini-3.5-flash")
    if settings.LLM_MODEL != "gemini-3.6-flash" and "gemini-3.6-flash" not in models_to_try:
        models_to_try.append("gemini-3.6-flash")

    client = genai.Client(api_key=settings.LLM_API_KEY)
    img_bytes = _pil_to_base64_bytes(image)

    for model in models_to_try:
        for attempt in range(3):
            try:
                image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                response = client.models.generate_content(
                    model=model,
                    contents=[image_part, _GEMINI_PROMPT],
                )
                raw = response.text.strip() if response.text else ""
                raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
                raw = re.sub(r"\s*```$", "", raw.strip())
                data = json.loads(raw)
                logger.info(f"Gemini vision success with model={model}")
                return data
            except Exception as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "overload" in err_str.lower():
                    wait = 2 * (attempt + 1)
                    logger.warning(f"Gemini {model} overloaded (attempt {attempt+1}/3), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.warning(f"Gemini vision failed (model={model}): {err_str[:150]}")
                    break  # Non-retryable error — try next model

    logger.warning("All Gemini vision attempts failed — falling back to heuristic analyzer.")
    return None


def _sanitize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalise LLM output to only accepted values."""
    category = str(data.get("category", "top")).lower().strip()
    if category not in _VALID_CATEGORIES:
        # Try to find closest match
        category = "top"

    valid_types = _VALID_TYPES.get(category, ["item"])
    garment_type = str(data.get("type", "")).lower().strip().replace(" ", "_")
    if garment_type not in valid_types:
        garment_type = valid_types[0]

    colour = str(data.get("colour", "neutral")).lower().strip()
    if colour not in _VALID_COLOURS:
        colour = "neutral"

    sec = data.get("secondary_colour")
    secondary_colour = str(sec).lower().strip() if sec else None
    if secondary_colour and secondary_colour not in _VALID_COLOURS:
        secondary_colour = None

    pattern = str(data.get("pattern", "solid")).lower().strip()
    if pattern not in _VALID_PATTERNS:
        pattern = "solid"

    formality = float(data.get("formality", 0.5))
    formality = round(max(0.0, min(1.0, formality)), 2)

    style_map = {
        "casual": "casual", "smart_casual": "smart_casual", "semi_formal": "semi_formal",
        "formal": "formal", "elegant": "elegant", "streetwear": "streetwear", "minimalist": "minimalist",
    }
    style = style_map.get(str(data.get("style", "")).lower().strip(), None)
    if style is None:
        # derive from formality
        if formality >= 0.80:
            style = "formal"
        elif formality >= 0.60:
            style = "smart_casual"
        elif formality >= 0.40:
            style = "semi_formal"
        else:
            style = "casual"

    sleeve_type = data.get("sleeve_type")
    material = data.get("material")

    confidence = float(data.get("confidence", 0.85))
    confidence = round(max(0.0, min(1.0, confidence)), 2)

    return {
        "category": category,
        "type": garment_type,
        "colour": colour,
        "secondary_colour": secondary_colour,
        "pattern": pattern,
        "formality": formality,
        "style": style,
        "sleeve_type": sleeve_type if isinstance(sleeve_type, str) else None,
        "material": material if isinstance(material, str) else None,
        "confidence": confidence,
        "backend": "gemini_vision",
    }


def analyze_with_gemini(image: Image.Image) -> Optional[ClothingAttributesDetected]:
    """
    Analyze a PIL image with Gemini Vision.
    Returns ClothingAttributesDetected on success, None on failure.
    """
    if settings.LLM_PROVIDER != "gemini" or not settings.LLM_API_KEY:
        return None

    raw = _call_gemini_vision(image)
    if not raw:
        return None

    try:
        clean = _sanitize(raw)
        logger.info(
            f"Gemini vision: {clean['category']}/{clean['type']} "
            f"({clean['colour']}, {clean['pattern']}) conf={clean['confidence']} "
            f"[{clean['backend']}]"
        )
        return ClothingAttributesDetected(
            category=clean["category"],
            type=clean["type"],
            colour=clean["colour"],
            secondary_colour=clean["secondary_colour"],
            pattern=clean["pattern"],
            style=clean["style"],
            sleeve_type=clean["sleeve_type"],
            formality=clean["formality"],
            material=clean["material"],
            confidence=clean["confidence"],
            color_palette=[clean["colour"]],
        )
    except Exception as e:
        logger.warning(f"Gemini vision result sanitization failed: {e}")
        return None
