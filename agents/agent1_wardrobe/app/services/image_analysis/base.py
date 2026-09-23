"""
Abstract Base Class for Clothing Image Analysis.
Ensures pluggability between local lightweight CV models and deep learning / CLIP backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from PIL import Image

from app.schemas.wardrobe import ClothingAttributesDetected


class BaseImageAnalyzer(ABC):
    """
    Abstract interface for clothing image attribute detection.
    """

    @abstractmethod
    def analyze_image(self, image: Image.Image) -> ClothingAttributesDetected:
        """
        Extract clothing attributes (category, type, colors, pattern, style, formality, confidence)
        from a PIL Image instance.
        """
        pass
