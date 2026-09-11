# Shared enums/constants used across agents.
# e.g. clothing categories, occasion types, style tags — add as they're defined
# during each agent's Stage 1 planning, don't pre-invent them here.

from enum import Enum


class ProductCategory(str, Enum):
    """
    Defined during Agent 2's Stage 1 (2026-09) because it crosses agent
    boundaries: Agent 1 flags missing categories, Agent 2 filters the product
    catalog by them, Agent 3 groups budget lines by them.

    Occasion and style taxonomies are still TBD -- add them here during
    Agent 1's own Stage 1 definition. Don't invent them ad hoc elsewhere.
    """

    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    BAG = "bag"
    JEWELRY = "jewelry"
    ACCESSORY = "accessory"
