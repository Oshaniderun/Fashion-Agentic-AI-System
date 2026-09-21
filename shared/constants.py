# Shared enums and constants used across FASHORA agents.
# Single source of truth across Agent 1, 2, 3, 4 and the Orchestrator.

from enum import Enum


class ProductCategory(str, Enum):
    """
    Standard clothing categories.
    Used by Agent 1 (wardrobe/missing), Agent 2 (retrieval), Agent 3 (budget), Agent 4 (outfit assembly).
    """
    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    BAG = "bag"
    JEWELRY = "jewelry"
    ACCESSORY = "accessory"


class OccasionType(str, Enum):
    """
    Normalized occasion taxonomy for NLP extraction and outfit requirements.
    """
    ENGAGEMENT = "engagement"
    WEDDING = "wedding"
    UNIVERSITY = "university"
    WORK = "work"
    FORMAL_EVENT = "formal_event"
    CASUAL = "casual"
    PARTY = "party"
    INTERVIEW = "interview"
    DINNER = "dinner"
    OTHER = "other"


class StyleType(str, Enum):
    """
    Normalized style preferences.
    """
    ELEGANT = "elegant"
    SEMI_FORMAL = "semi_formal"
    FORMAL = "formal"
    SMART_CASUAL = "smart_casual"
    CASUAL = "casual"
    STREETWEAR = "streetwear"
    MINIMALIST = "minimalist"
    OTHER = "other"


class ColorCategory(str, Enum):
    """
    Normalized standard color palette for vision detection and user preferences.
    """
    BLACK = "black"
    WHITE = "white"
    GREY = "grey"
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    PINK = "pink"
    BROWN = "brown"
    BEIGE = "beige"
    NAVY = "navy"
    # Tonal groups
    DARK = "dark"
    LIGHT = "light"
    NEUTRAL = "neutral"
    BRIGHT = "bright"
    PASTEL = "pastel"


class PatternType(str, Enum):
    """
    Normalized clothing patterns.
    """
    SOLID = "solid"
    STRIPED = "striped"
    CHECKED = "checked"
    FLORAL = "floral"
    PRINTED = "printed"
    POLKA_DOT = "polka_dot"
    TEXTURED = "textured"
    UNKNOWN = "unknown"
