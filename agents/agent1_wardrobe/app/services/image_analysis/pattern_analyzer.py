"""
Fabric Pattern Analysis Service.
Detects patterns (solid, striped, checked, printed, textured, unknown) using spatial gradient variance.
"""

from typing import Tuple
import numpy as np
from PIL import Image


class PatternAnalyzer:
    """Analyzes visual texture and spatial variation to detect patterns."""

    def detect_pattern(self, image: Image.Image) -> Tuple[str, float]:
        """
        Classifies clothing pattern from a garment-centric crop.
        Checked/gingham is preferred when BOTH axes show structure (not only stripes).
        """
        gray = image.convert("L")
        w, h = gray.size
        crop = gray.crop((int(w * 0.28), int(h * 0.22), int(w * 0.72), int(h * 0.88))).resize((160, 160))
        arr = np.array(crop, dtype=np.float32)

        luminance_std = float(np.std(arr))
        grad_x = np.diff(arr, axis=1)
        grad_y = np.diff(arr, axis=0)
        var_x = float(np.var(grad_x))
        var_y = float(np.var(grad_y))
        ratio_xy = (var_x + 1e-5) / (var_y + 1e-5)
        both_axes = min(var_x, var_y) > 120.0 and (var_x + var_y) > 300.0

        row_profile = arr.mean(axis=1)
        col_profile = arr.mean(axis=0)
        periodic = self._looks_periodic(row_profile) or self._looks_periodic(col_profile)
        grid_like = self._looks_periodic(row_profile) and self._looks_periodic(col_profile)

        if luminance_std < 12.0 and (var_x + var_y) < 160.0:
            return "solid", 0.94

        # Checked / gingham: 2D structure on both axes
        if grid_like and luminance_std > 12.0:
            return "checked", 0.88
        if both_axes and luminance_std > 14.0:
            return "checked", 0.82
        if periodic and both_axes:
            return "checked", 0.80

        # Stripes: strong 1-direction only (other axis weak)
        if (ratio_xy > 2.4 or ratio_xy < 0.42) and min(var_x, var_y) < 140.0 and luminance_std > 16.0:
            return "striped", 0.84

        if luminance_std > 45.0 and not both_axes:
            return "printed", 0.72

        if 12.0 <= luminance_std < 20.0 and (var_x + var_y) < 280.0:
            return "textured", 0.68

        if luminance_std < 22.0:
            return "solid", 0.75

        return "unknown", 0.45

    def _looks_periodic(self, profile: np.ndarray) -> bool:
        """Lag-based periodicity check for gingham/check grids."""
        p = profile - float(np.mean(profile))
        if float(np.std(p)) < 3.5:
            return False
        best = 0.0
        n = len(p)
        for lag in range(3, min(32, n // 3)):
            a, b = p[:-lag], p[lag:]
            denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-6
            corr = float(np.dot(a, b) / denom)
            if corr > best:
                best = corr
        return best > 0.28


pattern_analyzer = PatternAnalyzer()
