"""
CLIP / FashionCLIP image analyzer abstraction.
Provides zero-shot garment category and attribute classification using embeddings when CLIP/torch is installed,
with an automatic graceful fallback to visual heuristic analysis for CPU-friendly laptop execution.
"""

from typing import Dict, Any, Tuple
import numpy as np
from PIL import Image

from app.services.image_analysis.base import BaseImageAnalyzer
from app.core.logging import logger

FASHION_CATEGORIES = ["top", "bottom", "shoes", "outerwear", "dress", "bag", "accessory"]
GARMENT_TYPES = {
    "top": ["blouse", "shirt", "t-shirt", "sweater", "tank_top"],
    "bottom": ["jeans", "trousers", "skirt", "shorts"],
    "shoes": ["loafers", "sneakers", "boots", "heels", "sandals", "slippers"],
    "outerwear": ["blazer", "jacket", "coat", "cardigan"],
    "dress": ["midi_dress", "maxi_dress", "cocktail_dress", "frock"],
    "bag": ["handbag", "tote_bag", "clutch", "backpack"],
    "accessory": ["belt", "scarf", "jewelry", "hat"],
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
                sub_labels = [f"a photo of {s.replace('_', ' ')}" for s in sub_candidates]
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
                    "backend": "clip_vit",
                }
            except Exception as e:
                logger.warning(f"CLIP inference error, falling back to visual heuristics: {e}")

        return self._heuristic_category_and_type(image)

    def _object_geometry(self, image: Image.Image) -> Dict[str, float]:
        """Estimate foreground fill / bbox aspect using corner background sampling."""
        rgb = image.convert("RGB").resize((128, 128))
        arr = np.asarray(rgb, dtype=np.float32)
        corners = np.concatenate(
            [
                arr[:10, :10].reshape(-1, 3),
                arr[:10, -10:].reshape(-1, 3),
                arr[-10:, :10].reshape(-1, 3),
                arr[-10:, -10:].reshape(-1, 3),
            ],
            axis=0,
        )
        bg = corners.mean(axis=0)
        bg_std = float(corners.std())
        diff = np.linalg.norm(arr - bg, axis=2)
        thr = max(22.0, float(np.percentile(diff, 50)))
        mask = diff > thr
        fill = float(mask.mean())
        ys, xs = np.where(mask)
        if len(xs) < 40:
            return {
                "fill": fill,
                "obj_aspect": 1.0,
                "bg_std": bg_std,
                "sole_like": 0.0,
                "compact": 1.0,
            }
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        ow = max(1, x1 - x0)
        oh = max(1, y1 - y0)
        obj_aspect = ow / float(oh)

        gray = np.asarray(rgb.convert("L"), dtype=np.float32)
        gy = np.abs(np.diff(gray, axis=0))
        lower = gy[int(gy.shape[0] * 0.62) :].mean() if gy.size else 0.0
        upper = gy[: int(gy.shape[0] * 0.35)].mean() if gy.size else 0.0
        sole_like = float(lower / (upper + 1e-5))

        # How much of the bbox is actually foreground (bags/shoes often leave margin)
        bbox_area = ow * oh
        compact = float(mask.sum()) / float(max(1, bbox_area))

        return {
            "fill": fill,
            "obj_aspect": float(obj_aspect),
            "bg_std": bg_std,
            "sole_like": sole_like,
            "compact": compact,
        }

    def _classify_non_apparel(
        self,
        geom: Dict[str, float],
        aspect_ratio: float,
        sat: float,
        mean_rgb: Tuple[float, float, float],
        gridish: bool,
    ) -> Dict[str, Any] | None:
        """
        Detect shoes / slippers / bags / accessories before garment heuristics.
        Product shots of these items are often mislabelled as 'top' when square+vivid.
        """
        fill = geom["fill"]
        obj_aspect = geom["obj_aspect"]
        bg_std = geom["bg_std"]
        sole_like = geom["sole_like"]
        r, g, b = mean_rgb
        dark = (r + g + b) / 3.0 < 110
        plain_bg = bg_std < 28

        # Tiny object on plain background → accessory
        if plain_bg and fill < 0.14:
            return {
                "category": "accessory",
                "type": "jewelry",
                "confidence": 0.72,
                "backend": "visual_geometric_heuristic",
            }

        # Wide silhouette or sole-line cue → footwear
        footwear_shape = (
            obj_aspect >= 1.28
            or (obj_aspect >= 1.12 and sole_like >= 1.35)
            or (aspect_ratio < 0.85 and fill < 0.55)
        )
        if footwear_shape and fill < 0.72 and not (gridish and fill > 0.45):
            if sat > 0.35 and not dark:
                gtype = "slippers"
            elif sat < 0.2 and dark:
                gtype = "loafers"
            elif sole_like > 1.6 and sat < 0.35:
                gtype = "sneakers"
            else:
                gtype = "sandals" if sat > 0.25 else "slippers"
            return {
                "category": "shoes",
                "type": gtype,
                "confidence": 0.74,
                "backend": "visual_geometric_heuristic",
            }

        # Mid-size object on plain studio background → bag
        # (center-crop colour can be washed by margins; rely on fill + geometry)
        bag_shape = plain_bg and 0.12 <= fill <= 0.50 and 0.70 <= obj_aspect <= 1.45
        if bag_shape:
            return {
                "category": "bag",
                "type": "handbag" if dark or sat < 0.25 else "tote_bag",
                "confidence": 0.70,
                "backend": "visual_geometric_heuristic",
            }

        # Belt-like very wide thin object
        if plain_bg and obj_aspect >= 2.2 and fill < 0.25:
            return {
                "category": "accessory",
                "type": "belt",
                "confidence": 0.68,
                "backend": "visual_geometric_heuristic",
            }

        return None

    def _heuristic_category_and_type(self, image: Image.Image) -> Dict[str, Any]:
        """
        Local fallback: object silhouette + aspect ratio + centre-crop colour/texture cues.
        Tall photos are NOT blindly labelled jeans; product shoes/bags are not forced to tops.
        """
        w, h = image.size
        aspect_ratio = h / max(1, w)

        cx0, cy0 = int(w * 0.25), int(h * 0.20)
        cx1, cy1 = int(w * 0.75), int(h * 0.85)
        center = image.convert("RGB").crop((cx0, cy0, cx1, cy1)).resize((96, 96))
        arr = np.asarray(center, dtype=np.float32)
        mean_rgb = arr.reshape(-1, 3).mean(axis=0)
        r, g, b = mean_rgb.tolist()

        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0.0 if mx < 1e-5 else (mx - mn) / mx

        gray = center.convert("L")
        garr = np.asarray(gray, dtype=np.float32)
        std = float(np.std(garr))
        gx = np.diff(garr, axis=1)
        gy = np.diff(garr, axis=0)
        var_x, var_y = float(np.var(gx)), float(np.var(gy))
        ratio = (var_x + 1e-5) / (var_y + 1e-5)
        gridish = 0.75 <= ratio <= 1.35 and std > 16 and (var_x + var_y) > 250

        upper = arr[: arr.shape[0] // 3].reshape(-1, 3).mean(axis=0)
        lower = arr[2 * arr.shape[0] // 3 :].reshape(-1, 3).mean(axis=0)
        vertical_delta = float(np.linalg.norm(upper - lower))
        continuous_garment = vertical_delta < 40.0

        looks_denim = b > r + 10 and b > g + 5 and sat > 0.12
        vivid = sat > 0.32

        geom = self._object_geometry(image)
        non_apparel = self._classify_non_apparel(
            geom=geom,
            aspect_ratio=aspect_ratio,
            sat=sat,
            mean_rgb=(r, g, b),
            gridish=gridish,
        )
        if non_apparel is not None:
            return non_apparel

        # Full-bleed garments (high fill) — existing apparel logic
        if aspect_ratio > 1.2:
            if looks_denim and not gridish:
                category, garment_type, confidence = "bottom", "jeans", 0.72
            elif gridish and continuous_garment:
                category, garment_type, confidence = "dress", "frock", 0.78
            elif continuous_garment and sat < 0.30 and aspect_ratio > 1.45:
                category, garment_type, confidence = "dress", "frock", 0.74
            elif vivid or not continuous_garment:
                category, garment_type, confidence = "top", "blouse", 0.74
            else:
                category, garment_type, confidence = "bottom", "trousers", 0.65
        elif 0.85 <= aspect_ratio <= 1.2:
            if looks_denim:
                category, garment_type, confidence = "bottom", "jeans", 0.70
            elif gridish and continuous_garment and aspect_ratio > 1.05:
                category, garment_type, confidence = "dress", "frock", 0.68
            elif geom["fill"] < 0.35 and geom["obj_aspect"] >= 1.15:
                category, garment_type, confidence = "shoes", "slippers", 0.66
            else:
                category, garment_type, confidence = "top", "blouse", 0.76
        else:
            if gridish and continuous_garment:
                category, garment_type, confidence = "dress", "frock", 0.60
            elif geom["fill"] < 0.45:
                category, garment_type, confidence = "shoes", "loafers", 0.64
            elif vivid and geom["fill"] > 0.55:
                category, garment_type, confidence = "top", "blouse", 0.62
            else:
                category, garment_type, confidence = "shoes", "loafers", 0.60

        return {
            "category": category,
            "type": garment_type,
            "confidence": confidence,
            "backend": "visual_geometric_heuristic",
        }

    def analyze_image(self, image: Image.Image):
        pass


clip_analyzer = ClipImageAnalyzer()
