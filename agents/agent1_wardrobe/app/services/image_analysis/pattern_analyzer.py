"""
Fabric Pattern Analysis Service.
Detects patterns (solid, striped, checked, printed, textured, unknown) using spatial gradient variance.
"""

from typing import Tuple
import numpy as np
from PIL import Image

from app.core.logging import logger


class PatternAnalyzer:
    """Analyzes visual texture and spatial variation to detect patterns."""

    def detect_pattern(self, image: Image.Image) -> Tuple[str, float]:
        """
        Calculates directional gradient variance and texture standard deviation
        to classify clothing pattern.
        """
        # Convert to grayscale and crop central 60% of garment to avoid background edges
        gray = image.convert("L").resize((150, 150))
        arr = np.array(gray, dtype=np.float32)

        h, w = arr.shape
        crop_y, crop_x = int(h * 0.2), int(w * 0.2)
        center_patch = arr[crop_y:h - crop_y, crop_x:w - crop_x]

        # Calculate standard deviation of luminance
        luminance_std = float(np.std(center_patch))

        # Calculate horizontal and vertical gradients
        grad_x = np.diff(center_patch, axis=1)
        grad_y = np.diff(center_patch, axis=0)

        var_x = float(np.var(grad_x))
        var_y = float(np.var(grad_y))

        # 1. Very low variance indicates a clean solid color fabric
        if luminance_std < 14.0 and (var_x + var_y) < 180.0:
            return "solid", 0.94

        # 2. Strong directional asymmetry indicates stripes
        ratio_xy = (var_x + 1e-5) / (var_y + 1e-5)
        if ratio_xy > 2.2 or ratio_xy < 0.45:
            if luminance_std > 20.0:
                return "striped", 0.86

        # 3. High balanced variance with repetitive grid characteristics indicates checked
        if 18.0 <= luminance_std <= 38.0 and 0.8 <= ratio_xy <= 1.25 and (var_x + var_y) > 400.0:
            return "checked", 0.78

        # 4. High luminance variance indicates floral or print
        if luminance_std > 40.0:
            return "printed", 0.75

        # 5. Moderate variance with fine grain
        if 14.0 <= luminance_std < 22.0:
            return "textured", 0.70

        # Default to solid or unknown if ambiguous
        if luminance_std < 25.0:
            return "solid", 0.80

        return "unknown", 0.50


pattern_analyzer = PatternAnalyzer()
