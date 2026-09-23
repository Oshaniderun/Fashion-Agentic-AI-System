"""
Master Clothing Image Analyzer.
Pipeline:
  1. Gemini Vision API (primary) — accurate multimodal LLM analysis
  2. CLIP / heuristic fallback — if Gemini is unavailable or fails

Enforces Responsible AI standards:
  - No demographic, gender, body-shape, or skin-tone judgments
  - Only visible clothing attributes are reported
  - User can edit all detected attributes after upload
"""

from typing import Optional
from PIL import Image

from app.schemas.wardrobe import ClothingAttributesDetected
from app.services.image_analysis.base import BaseImageAnalyzer
from app.services.image_analysis.color_analyzer import color_analyzer
from app.services.image_analysis.pattern_analyzer import pattern_analyzer
from app.services.image_analysis.clip_analyzer import clip_analyzer
from app.services.image_analysis.gemini_vision import analyze_with_gemini
from app.core.config import settings
from app.core.logging import logger


class ClothingImageAnalyzer(BaseImageAnalyzer):
    """
    Orchestrates clothing image analysis using the best available backend.

    Backend priority:
      1. Gemini Vision (LLM_PROVIDER=gemini + LLM_API_KEY set)
      2. CLIP (if torch + transformers installed)
      3. Local colour/geometry heuristics (always available, least accurate)

    Color + pattern detection always uses the local analyzers regardless of
    category/type backend, since K-Means color clustering is more reliable
    than asking the LLM for exact hex codes.
    """

    def analyze_image(self, image: Image.Image) -> ClothingAttributesDetected:
        """
        Extract structured clothing attributes from a PIL Image.
        Always editable by the user after upload.
        """
        # ── Step 1: Color + pattern via local analyzers (always accurate) ─────
        color_data = color_analyzer.analyze_colors(image)
        primary_color = color_data["primary_color"]
        secondary_color = color_data["secondary_color"]
        color_conf = color_data["confidence"]
        palette = color_data["palette"]

        pattern, pattern_conf = pattern_analyzer.detect_pattern(image)

        # ── Step 2: Category + type via best available backend ────────────────
        gemini_result: Optional[ClothingAttributesDetected] = None

        if settings.LLM_PROVIDER == "gemini" and settings.LLM_API_KEY:
            gemini_result = analyze_with_gemini(image)

        if gemini_result is not None:
            # Gemini succeeded — use its category/type/style/formality/material/sleeve
            # but override colour + pattern with our more reliable local analyzers
            return ClothingAttributesDetected(
                category=gemini_result.category,
                type=gemini_result.type,
                colour=primary_color,          # local K-Means is more reliable
                secondary_colour=secondary_color,
                pattern=pattern,               # local gradient analysis
                style=gemini_result.style,
                sleeve_type=gemini_result.sleeve_type,
                formality=gemini_result.formality,
                material=gemini_result.material,
                confidence=round(
                    float(gemini_result.confidence * 0.6 + color_conf * 0.25 + pattern_conf * 0.15), 2
                ),
                color_palette=palette,
            )

        # ── Step 3: Fallback — CLIP or geometric heuristic ───────────────────
        logger.info("Gemini vision not available — using local heuristic analyzer.")
        cat_data = clip_analyzer.predict_category_and_type(image)
        category = cat_data["category"]
        garment_type = cat_data["type"]
        cat_conf = cat_data["confidence"]

        formality, inferred_style, sleeve_type, material = self._infer_style_and_formality(
            category=category,
            garment_type=garment_type,
            primary_color=primary_color,
            pattern=pattern,
        )

        overall_conf = round(float((cat_conf * 0.45) + (color_conf * 0.35) + (pattern_conf * 0.20)), 2)

        return ClothingAttributesDetected(
            category=category,
            type=garment_type,
            colour=primary_color,
            secondary_colour=secondary_color,
            pattern=pattern,
            style=inferred_style,
            sleeve_type=sleeve_type,
            formality=formality,
            material=material,
            confidence=overall_conf,
            color_palette=palette,
        )

    def _infer_style_and_formality(
        self,
        category: str,
        garment_type: str,
        primary_color: str,
        pattern: str,
    ) -> tuple[float, str, Optional[str], Optional[str]]:
        """
        Rule-based fashion reasoning: garment type + color → style & formality.
        Used only in the local heuristic fallback path.
        Neutral gender-inclusive terminology only.
        """
        formality_map = {
            "shirt": 0.85, "blouse": 0.70, "t-shirt": 0.30, "sweater": 0.55,
            "tank_top": 0.25, "crop_top": 0.25, "hoodie": 0.30, "kurta": 0.55,
            "trousers": 0.85, "chinos": 0.70, "jeans": 0.40, "skirt": 0.65,
            "shorts": 0.25, "leggings": 0.30, "palazzo": 0.55,
            "loafers": 0.70, "formal_shoes": 0.90, "sneakers": 0.35,
            "boots": 0.60, "heels": 0.85, "sandals": 0.30, "slippers": 0.20, "flats": 0.45,
            "blazer": 0.90, "jacket": 0.55, "coat": 0.75, "trench_coat": 0.70, "cardigan": 0.50,
            "cocktail_dress": 0.90, "midi_dress": 0.70, "maxi_dress": 0.75,
            "frock": 0.55, "jumpsuit": 0.60, "mini_dress": 0.60,
            "handbag": 0.55, "tote_bag": 0.45, "clutch": 0.65, "backpack": 0.35,
            "belt": 0.50, "scarf": 0.45, "jewelry": 0.55, "hat": 0.40,
        }

        formality = formality_map.get(garment_type, 0.50)
        if primary_color in ["black", "navy", "grey", "white"]:
            formality = min(1.0, formality + 0.05)
        elif primary_color in ["yellow", "orange", "pink"]:
            formality = max(0.1, formality - 0.05)

        if formality >= 0.80:
            style = "formal"
        elif formality >= 0.60:
            style = "smart_casual"
        elif formality >= 0.45:
            style = "semi_formal"
        elif formality >= 0.30:
            style = "casual"
        else:
            style = "streetwear"

        sleeve_type = None
        if category in ["top", "outerwear", "dress"]:
            if garment_type in ["blouse", "shirt", "blazer", "sweater", "coat", "midi_dress", "frock"]:
                sleeve_type = "long_sleeve"
            elif garment_type in ["t-shirt", "kurta"]:
                sleeve_type = "short_sleeve"
            elif garment_type in ["tank_top", "crop_top"]:
                sleeve_type = "sleeveless"

        material_map = {
            "jeans": "denim", "blouse": "silk_blend", "shirt": "cotton",
            "loafers": "leather", "formal_shoes": "leather", "trousers": "wool_blend",
            "t-shirt": "cotton", "blazer": "tailored_wool", "sneakers": "canvas_leather",
            "slippers": "fabric", "sandals": "leather", "frock": "cotton",
            "midi_dress": "fabric", "maxi_dress": "fabric", "handbag": "leather",
            "tote_bag": "fabric", "belt": "leather", "chinos": "cotton",
        }
        material = material_map.get(garment_type, "fabric")
        if pattern == "checked" and garment_type in ["frock", "midi_dress", "shirt"]:
            material = "cotton"

        return round(formality, 2), style, sleeve_type, material


master_image_analyzer = ClothingImageAnalyzer()


