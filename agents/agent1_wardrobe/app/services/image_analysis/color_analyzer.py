"""
Color Analysis and Extraction Service.
Extracts dominant colors using K-Means clustering, filters background, and maps to normalized color ontology.
"""

import colorsys
from typing import List, Tuple, Dict, Any
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from app.core.logging import logger

# Canonical reference color coordinates in HSV space (Hue 0-360, Sat 0-100, Val 0-100)
COLOR_PALETTE_HSV = {
    "black": (0, 0, 10),
    "white": (0, 0, 95),
    "grey": (0, 0, 50),
    "navy": (220, 80, 30),
    "blue": (210, 80, 75),
    "beige": (40, 25, 85),
    "brown": (25, 70, 40),
    "red": (0, 85, 75),
    "orange": (30, 90, 85),
    "yellow": (55, 85, 90),
    "green": (130, 70, 60),
    "purple": (280, 75, 65),
    "pink": (330, 50, 85),
}

NEUTRAL_COLORS = {"black", "white", "grey", "navy", "beige", "brown"}


class ColorAnalyzer:
    """Performs practical dominant color extraction and normalized category mapping."""

    def __init__(self, n_clusters: int = 4):
        self.n_clusters = n_clusters

    def analyze_colors(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extracts dominant primary and secondary colors and tonal group from the clothing image.
        Uses a center crop and filters likely scenic background pixels (sky/water).
        """
        w, h = image.size
        # Focus on the garment region; full-frame person photos pull sunset/water into clusters
        cropped = image.convert("RGB").crop((int(w * 0.28), int(h * 0.22), int(w * 0.72), int(h * 0.88)))
        img_small = cropped.resize((120, 120))
        pixels = np.array(img_small).reshape(-1, 3).astype(np.float32)

        # Drop near-white + strong blue water + strong orange sunset + near-black UI/shadows
        r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
        near_white = (r > 235) & (g > 235) & (b > 235)
        near_black = (r < 35) & (g < 35) & (b < 35)
        water_blue = (b > r + 25) & (b > g + 15) & (b > 120)
        sunset_orange = (r > 180) & (g > 90) & (g < 180) & (b < 90) & (r > b + 60)
        mask = ~(near_white | near_black | water_blue | sunset_orange)
        filtered_pixels = pixels[mask]

        if len(filtered_pixels) < 50:
            filtered_pixels = pixels

        k = min(self.n_clusters, len(filtered_pixels))
        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        kmeans.fit(filtered_pixels)

        labels, counts = np.unique(kmeans.labels_, return_counts=True)
        sorted_indices = np.argsort(-counts)

        palette_hex: List[str] = []
        cluster_weights: List[float] = []
        cluster_colors: List[Tuple[str, str, float]] = []

        total_pixels = len(filtered_pixels)

        for idx in sorted_indices:
            center = kmeans.cluster_centers_[idx].astype(int)
            hex_code = f"#{center[0]:02x}{center[1]:02x}{center[2]:02x}"
            palette_hex.append(hex_code)
            weight = float(counts[idx] / total_pixels)
            cluster_weights.append(weight)

            name, tone, conf = self._map_rgb_to_color_name(center[0], center[1], center[2])
            cluster_colors.append((name, tone, conf))

        primary_name, primary_tone, primary_conf = cluster_colors[0]
        secondary_name = None
        if len(cluster_colors) > 1 and cluster_weights[1] >= 0.15:
            cand_sec = cluster_colors[1][0]
            if cand_sec != primary_name:
                secondary_name = cand_sec

        return {
            "primary_color": primary_name,
            "secondary_color": secondary_name,
            "tone": primary_tone,
            "confidence": round(float(primary_conf * min(1.0, cluster_weights[0] + 0.3)), 2),
            "palette": palette_hex[:4]
        }

    def _map_rgb_to_color_name(self, r: int, g: int, b: int) -> Tuple[str, str, float]:
        """Maps an RGB tuple to a normalized color category and tonal classification."""
        # Convert to HSV (h in 0-360, s in 0-100, v in 0-100)
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        h_deg = h * 360
        s_pct = s * 100
        v_pct = v * 100

        # Tone determination
        if v_pct < 25:
            tone = "dark"
        elif v_pct > 80 and s_pct < 30:
            tone = "light"
        elif s_pct < 20:
            tone = "neutral"
        elif s_pct > 65 and v_pct > 60:
            tone = "bright"
        elif s_pct < 50 and v_pct > 70:
            tone = "pastel"
        else:
            tone = "neutral"

        # Explicit low-saturation / extreme value boundaries
        if v_pct < 15:
            return "black", "dark", 0.95
        if v_pct > 88 and s_pct < 12:
            return "white", "light", 0.95

        # Beige / tan before generic grey — gingham beige+white averages look desaturated
        if 20 <= h_deg <= 55 and s_pct <= 45 and v_pct > 55:
            return "beige", "neutral", 0.86

        if s_pct < 15 and 15 <= v_pct <= 85:
            return "grey", "neutral", 0.90

        # Navy vs Blue distinction
        if 200 <= h_deg <= 245 and v_pct < 45 and s_pct > 30:
            return "navy", "dark", 0.92

        # Beige check (low-sat yellow/orange at high brightness)
        if 25 <= h_deg <= 50 and 10 <= s_pct <= 40 and v_pct > 65:
            return "beige", "neutral", 0.88

        # Brown check (orange/red at low-to-medium brightness)
        if 10 <= h_deg <= 40 and s_pct > 30 and v_pct < 55:
            return "brown", "dark", 0.88

        # General Hue-based classification
        if h_deg < 15 or h_deg >= 345:
            return "red", tone, 0.89
        elif 15 <= h_deg < 42:
            return "orange", tone, 0.87
        elif 42 <= h_deg < 68:
            return "yellow", tone, 0.88
        elif 68 <= h_deg < 165:
            return "green", tone, 0.90
        elif 165 <= h_deg < 255:
            return "blue", tone, 0.91
        elif 255 <= h_deg < 315:
            return "purple", tone, 0.86
        else:
            return "pink", tone, 0.88


color_analyzer = ColorAnalyzer()
