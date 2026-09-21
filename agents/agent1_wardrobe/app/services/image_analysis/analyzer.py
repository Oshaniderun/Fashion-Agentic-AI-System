"""
Master Clothing Image Analyzer.
Combines color clustering, pattern gradient analysis, category/type estimation,
and style/formality reasoning into structured, editable attributes.
Enforces Responsible AI standards (no demographic, body-shape, or sensitive judgments).
"""

from typing import Dict, Any, Optional
from PIL import Image

from app.schemas.wardrobe import ClothingAttributesDetected
from app.services.image_analysis.base import BaseImageAnalyzer
from app.services.image_analysis.color_analyzer import color_analyzer
from app.services.image_analysis.pattern_analyzer import pattern_analyzer
from app.services.image_analysis.clip_analyzer import clip_analyzer
from app.core.logging import logger


class ClothingImageAnalyzer(BaseImageAnalyzer):
    """
    Orchestrates specialized CV components to analyze uploaded clothing images.
    """

    def analyze_image(self, image: Image.Image) -> ClothingAttributesDetected:
        """
        Extracts comprehensive clothing attributes from a PIL Image.
        """
        # 1. Color extraction
        color_data = color_analyzer.analyze_colors(image)
        primary_color = color_data["primary_color"]
        secondary_color = color_data["secondary_color"]
        tone = color_data["tone"]
        color_conf = color_data["confidence"]
        palette = color_data["palette"]

        # 2. Pattern detection
        pattern, pattern_conf = pattern_analyzer.detect_pattern(image)

        # 3. Category & garment type detection
        cat_data = clip_analyzer.predict_category_and_type(image)
        category = cat_data["category"]
        garment_type = cat_data["type"]
        cat_conf = cat_data["confidence"]

        # 4. Formality & style inference
        formality, inferred_style, sleeve_type, material = self._infer_style_and_formality(
            category=category,
            garment_type=garment_type,
            primary_color=primary_color,
            pattern=pattern
        )

        # 5. Combined calibrated confidence score
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
            color_palette=palette
        )

    def _infer_style_and_formality(
        self,
        category: str,
        garment_type: str,
        primary_color: str,
        pattern: str
    ) -> tuple[float, str, Optional[str], Optional[str]]:
        """
        Rule-based fashion reasoning mapping garment type and colors to style & formality.
        Neutral gender-inclusive terminology only.
        """
        # Formality base scores
        formality_map = {
            # Tops
            "shirt": 0.85,
            "blouse": 0.70,
            "t-shirt": 0.30,
            "sweater": 0.55,
            "tank_top": 0.25,
            # Bottoms
            "trousers": 0.85,
            "jeans": 0.40,
            "skirt": 0.65,
            "shorts": 0.25,
            # Shoes
            "loafers": 0.70,
            "sneakers": 0.35,
            "boots": 0.60,
            "heels": 0.85,
            "sandals": 0.30,
            # Outerwear
            "blazer": 0.90,
            "jacket": 0.55,
            "coat": 0.75,
            # Dresses
            "cocktail_dress": 0.90,
            "midi_dress": 0.70,
        }

        formality = formality_map.get(garment_type, 0.50)

        # Tonal adjustment: dark / neutral tones slightly raise formality
        if primary_color in ["black", "navy", "grey", "white"]:
            formality = min(1.0, formality + 0.05)
        elif primary_color in ["yellow", "orange", "pink"]:
            formality = max(0.1, formality - 0.05)

        # Style classification
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

        # Sleeve type where applicable
        sleeve_type = None
        if category in ["top", "outerwear"]:
            if garment_type in ["blouse", "shirt", "blazer", "sweater", "coat"]:
                sleeve_type = "long_sleeve"
            elif garment_type == "t-shirt":
                sleeve_type = "short_sleeve"
            elif garment_type == "tank_top":
                sleeve_type = "sleeveless"

        # Material heuristic
        material_map = {
            "jeans": "denim",
            "blouse": "silk_blend",
            "shirt": "cotton",
            "loafers": "leather",
            "trousers": "wool_blend",
            "t-shirt": "cotton",
            "blazer": "tailored_wool",
            "sneakers": "canvas_leather",
        }
        material = material_map.get(garment_type, "fabric")

        return round(formality, 2), style, sleeve_type, material


master_image_analyzer = ClothingImageAnalyzer()
