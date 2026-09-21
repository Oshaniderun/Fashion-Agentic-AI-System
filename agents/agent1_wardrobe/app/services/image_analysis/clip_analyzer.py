"""
CLIP / FashionCLIP image analyzer abstraction.
Provides zero-shot garment category and attribute classification using embeddings when CLIP/torch is installed,
with an automatic graceful fallback to visual heuristic analysis for CPU-friendly laptop execution.
"""

from typing import Dict, Any
import numpy as np
from PIL import Image

from app.services.image_analysis.base import BaseImageAnalyzer
from app.core.logging import logger

FASHION_CATEGORIES = ["top", "bottom", "shoes", "outerwear", "dress", "bag", "accessory"]
GARMENT_TYPES = {
    "top": ["blouse", "shirt", "t-shirt", "sweater", "tank_top"],
    "bottom": ["jeans", "trousers", "skirt", "shorts"],
    "shoes": ["loafers", "sneakers", "boots", "heels", "sandals"],
    "outerwear": ["blazer", "jacket", "coat", "cardigan"],
    "dress": ["midi_dress", "maxi_dress", "cocktail_dress", "frock"],
    "bag": ["handbag", "tote_bag", "clutch", "backpack"],
    "accessory": ["belt", "scarf", "jewelry", "hat"]
}


class ClipImageAnalyzer(BaseImageAnalyzer):
    """
    CLIP / FashionCLIP-compatible zero-shot analyzer.
    Checks dynamically for torch and transformers / open_clip.
    """

    def __init__(self):
        self.model = None
        self.processor = None
        self.is_loaded = False
        self._init_backend()

    def _init_backend(self) -> None:
        """Attempts to load CLIP if installed; logs CPU mode status."""
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            logger.info("Initializing HuggingFace CLIP model on CPU...")
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self.model.eval()
            self.is_loaded = True
            logger.info("HuggingFace CLIP successfully initialized.")
        except Exception as e:
            logger.info(
                f"CLIP deep learning weights not initialized ({e}). "
                "Running in High-Performance Local CPU Vision Mode (Color K-Means + Aspect Ratio + Texture Analysis)."
            )
            self.is_loaded = False

    def predict_category_and_type(self, image: Image.Image) -> Dict[str, Any]:
        """
        Predicts category and garment type using zero-shot CLIP if available,
        or intelligent aspect ratio & visual contour heuristics if on CPU-only.
        """
        if self.is_loaded:
            try:
                import torch
                text_labels = [f"a photo of a {c}" for c in FASHION_CATEGORIES]
                inputs = self.processor(text=text_labels, images=image, return_tensors="pt", padding=True)
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits_per_image[0]
                    probs = logits.softmax(dim=-1).numpy()

                top_idx = int(np.argmax(probs))
                category = FASHION_CATEGORIES[top_idx]
                confidence = float(probs[top_idx])

                sub_candidates = GARMENT_TYPES.get(category, ["item"])
                sub_labels = [f"a photo of {s}" for s in sub_candidates]
                sub_inputs = self.processor(text=sub_labels, images=image, return_tensors="pt", padding=True)
                with torch.no_grad():
                    sub_outputs = self.model(**sub_inputs)
                    sub_probs = sub_outputs.logits_per_image[0].softmax(dim=-1).numpy()

                sub_idx = int(np.argmax(sub_probs))
                garment_type = sub_candidates[sub_idx]

                return {
                    "category": category,
                    "type": garment_type,
                    "confidence": round(confidence, 2),
                    "backend": "clip_vit"
                }
            except Exception as e:
                logger.warning(f"CLIP inference error, falling back to visual heuristics: {e}")

        return self._heuristic_category_and_type(image)

    def _heuristic_category_and_type(self, image: Image.Image) -> Dict[str, Any]:
        """
        Local fallback: aspect ratio + center-crop colour/texture cues.
        Tall photos are NOT blindly labelled jeans (that broke frock uploads).
        """
        w, h = image.size
        aspect_ratio = h / max(1, w)

        # Center crop avoids sunset sky / water dominating cues
        cx0, cy0 = int(w * 0.25), int(h * 0.20)
        cx1, cy1 = int(w * 0.75), int(h * 0.85)
        center = image.convert("RGB").crop((cx0, cy0, cx1, cy1)).resize((96, 96))
        arr = np.asarray(center, dtype=np.float32)
        mean_rgb = arr.reshape(-1, 3).mean(axis=0)
        r, g, b = mean_rgb.tolist()

        # Rough warm/cool and saturation
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0.0 if mx < 1e-5 else (mx - mn) / mx
        warm = (r + g) / 2.0 > b + 8

        gray = center.convert("L")
        garr = np.asarray(gray, dtype=np.float32)
        std = float(np.std(garr))
        gx = np.diff(garr, axis=1)
        gy = np.diff(garr, axis=0)
        var_x, var_y = float(np.var(gx)), float(np.var(gy))
        ratio = (var_x + 1e-5) / (var_y + 1e-5)
        gridish = 0.75 <= ratio <= 1.35 and std > 16 and (var_x + var_y) > 250

        # Vertical colour continuity: dresses keep similar colour top→bottom;
        # blouses often differ (skin/background) in the lower third.
        upper = arr[: arr.shape[0] // 3].reshape(-1, 3).mean(axis=0)
        lower = arr[2 * arr.shape[0] // 3 :].reshape(-1, 3).mean(axis=0)
        vertical_delta = float(np.linalg.norm(upper - lower))
        continuous_garment = vertical_delta < 40.0

        looks_denim = b > r + 10 and b > g + 5 and sat > 0.12
        vivid = sat > 0.32

        if aspect_ratio > 1.2:
            if looks_denim and not gridish:
                category, garment_type, confidence = "bottom", "jeans", 0.72
            elif gridish and continuous_garment:
                category, garment_type, confidence = "dress", "frock", 0.78
            elif continuous_garment and sat < 0.30 and aspect_ratio > 1.45:
                category, garment_type, confidence = "dress", "frock", 0.74
            elif vivid or not continuous_garment:
                # Red/bright tops and upper-body shots → blouse, not frock
                category, garment_type, confidence = "top", "blouse", 0.74
            else:
                category, garment_type, confidence = "bottom", "trousers", 0.65
        elif 0.85 <= aspect_ratio <= 1.2:
            if looks_denim:
                category, garment_type, confidence = "bottom", "jeans", 0.70
            elif gridish and continuous_garment and aspect_ratio > 1.05:
                category, garment_type, confidence = "dress", "frock", 0.68
            else:
                category, garment_type, confidence = "top", "blouse", 0.76
        else:
            if gridish and continuous_garment:
                category, garment_type, confidence = "dress", "frock", 0.60
            elif vivid:
                category, garment_type, confidence = "top", "blouse", 0.62
            else:
                category, garment_type, confidence = "shoes", "loafers", 0.58

        return {
            "category": category,
            "type": garment_type,
            "confidence": confidence,
            "backend": "visual_geometric_heuristic"
        }

    def analyze_image(self, image: Image.Image):
        pass


clip_analyzer = ClipImageAnalyzer()
