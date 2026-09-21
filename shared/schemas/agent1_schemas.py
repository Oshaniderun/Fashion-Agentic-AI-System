"""
Agent 1 — Style & Wardrobe Intelligence
Shared Pydantic contracts between Agent 1 and downstream agents (Agents 2, 3, 4, Orchestrator).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

from shared.constants import (  # noqa: F401 — kept for schema consumers / docs
    ProductCategory,
    OccasionType,
    StyleType,
    ColorCategory,
    PatternType,
)


# ---------------------------------------------------------------------------
# Core Sub-Models
# ---------------------------------------------------------------------------

class UserRequirements(BaseModel):
    occasion: Optional[str] = Field(
        None, description="Target occasion (e.g. 'engagement', 'wedding', 'university'). None if unspecified."
    )
    style: List[str] = Field(
        default_factory=list,
        description="Target style preferences (e.g. ['elegant', 'semi_formal']). Empty list if unspecified."
    )
    colour_preferences: List[str] = Field(
        default_factory=list,
        description="Preferred color families (e.g. ['dark', 'neutral']). Empty list if unspecified."
    )
    excluded_colours: List[str] = Field(
        default_factory=list,
        description="Colors the user explicitly dislikes or wishes to exclude (e.g. ['bright'])."
    )
    budget: Optional[float] = Field(
        None, gt=0, description="Stated user budget ceiling in LKR. None if unmentioned; never hallucinated."
    )
    requested_categories: List[str] = Field(
        default_factory=list,
        description="Explicit garment categories requested (e.g. ['dress'] for frock/dress).",
    )
    requested_types: List[str] = Field(
        default_factory=list,
        description="Explicit garment type words from the request (e.g. ['frock', 'blouse']).",
    )
    pattern_preferences: List[str] = Field(
        default_factory=list,
        description="Requested patterns (e.g. ['checked', 'striped']). Empty if unspecified.",
    )
    additional_preferences: List[str] = Field(
        default_factory=list,
        description="Additional user preferences or constraints extracted from the text."
    )


class WardrobeSummaryItem(BaseModel):
    wardrobe_id: str = Field(..., description="Unique identifier for the item (e.g. 'W001').")
    category: str = Field(..., description="Category, e.g. 'top', 'bottom', 'shoes'.")
    type: str = Field(..., description="Specific garment type, e.g. 'blouse', 'jeans', 'loafer'.")
    colour: str = Field(..., description="Primary detected or user-confirmed color.")
    secondary_colour: Optional[str] = Field(None, description="Secondary color if detected.")
    pattern: str = Field("solid", description="Pattern type, e.g. 'solid', 'striped', 'floral'.")
    style: str = Field("casual", description="Style category, e.g. 'smart_casual', 'formal'.")
    sleeve_type: Optional[str] = Field(None, description="Sleeve type where applicable.")
    formality: float = Field(0.5, ge=0.0, le=1.0, description="Formality score from 0.0 (casual) to 1.0 (formal).")
    material: Optional[str] = Field(None, description="Approximate material if detectable/confirmed.")
    image_url: Optional[str] = Field(None, description="URL or relative path to the clothing item image.")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Detection or confirmation confidence.")


class OutfitRequirements(BaseModel):
    required_categories: List[str] = Field(
        default_factory=list,
        description="Categories required to assemble a complete outfit for this occasion."
    )
    available_categories: List[str] = Field(
        default_factory=list,
        description="Required categories that the user already has in their wardrobe."
    )
    missing_categories: List[str] = Field(
        default_factory=list,
        description="Required categories missing from the user's wardrobe (for Agent 2 retrieval)."
    )
    optional_categories: List[str] = Field(
        default_factory=list,
        description="Nice-to-have complement categories (e.g. 'bag', 'accessory')."
    )


class CompatibilityDetails(BaseModel):
    style: str = Field(..., description="Overall synthesized style of the combination.")
    occasion_suitability: str = Field(..., description="Qualitative rating: 'high', 'moderate', 'low'.")
    colour_compatibility: str = Field(..., description="Qualitative rating: 'excellent', 'good', 'moderate', 'clashing'.")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized compatibility score (0.0 to 1.0).")
    explanation: str = Field(..., description="Explainable rationale grounded in color and style theory.")


class ConfidenceMetrics(BaseModel):
    overall: float = Field(..., ge=0.0, le=1.0, description="Overall pipeline confidence.")
    vision: Optional[float] = Field(None, ge=0.0, le=1.0, description="Image analysis confidence.")
    nlp: Optional[float] = Field(None, ge=0.0, le=1.0, description="NLP extraction confidence.")


class Agent2AvailableItem(BaseModel):
    """Compact owned item Agent 2 can use for complementary retrieval context."""
    wardrobe_id: str
    category: str
    type: str
    colour: str


class Agent2WardrobeStatus(BaseModel):
    available_categories: List[str] = Field(default_factory=list)
    missing_categories: List[str] = Field(default_factory=list)


class Agent2SearchRequirement(BaseModel):
    """
    Search brief for Agent 2 (Information Retrieval).
    Dual field names kept for backward compatibility with earlier handoffs.
    """
    categories: List[str] = Field(
        default_factory=list,
        description="Categories Agent 2 should retrieve (same as missing_categories).",
    )
    missing_categories: List[str] = Field(
        default_factory=list,
        description="Alias of categories — categories missing from wardrobe.",
    )
    style: List[str] = Field(default_factory=list, description="Target styles to filter.")
    colour_preferences: List[str] = Field(
        default_factory=list, description="Preferred colours / colour families for search."
    )
    colour: List[str] = Field(
        default_factory=list, description="Alias of colour_preferences (legacy)."
    )
    pattern_preferences: List[str] = Field(
        default_factory=list, description="Target patterns (checked, striped, etc.)."
    )
    pattern: List[str] = Field(
        default_factory=list, description="Alias of pattern_preferences (legacy)."
    )
    occasion: Optional[str] = Field(None, description="Event context.")
    maximum_price: Optional[float] = Field(None, description="Max price / remaining budget in LKR.")
    budget_remaining: Optional[float] = Field(
        None, description="Alias of maximum_price (legacy)."
    )
    query_text: Optional[str] = Field(
        None, description="Deduped expanded query for BM25 / vector search."
    )

    @model_validator(mode="after")
    def _sync_aliases(self):
        cats = self.categories or self.missing_categories
        self.categories = list(cats)
        self.missing_categories = list(cats)
        colours = self.colour_preferences or self.colour
        self.colour_preferences = list(colours)
        self.colour = list(colours)
        patterns = self.pattern_preferences or self.pattern
        self.pattern_preferences = list(patterns)
        self.pattern = list(patterns)
        price = self.maximum_price if self.maximum_price is not None else self.budget_remaining
        self.maximum_price = price
        self.budget_remaining = price
        return self


class Agent2HandoffPayload(BaseModel):
    """
    Full Agent 1 → Agent 2 handoff package.
    Richer than a bare query_text string so Agent 2 can filter structured fields.
    """
    request_id: str
    user_requirements: UserRequirements
    wardrobe_status: Agent2WardrobeStatus
    available_items: List[Agent2AvailableItem] = Field(default_factory=list)
    search_requirements: Agent2SearchRequirement


# ---------------------------------------------------------------------------
# Output Contract: Agent 1 Response
# ---------------------------------------------------------------------------

class Agent1OutputContract(BaseModel):
    request_id: str = Field(..., description="Correlation ID carried through the entire system.")
    user_requirements: UserRequirements
    wardrobe: List[WardrobeSummaryItem] = Field(
        default_factory=list, description="Wardrobe items owned by the user."
    )
    outfit_requirements: OutfitRequirements
    compatible_items: List[str] = Field(
        default_factory=list, description="IDs of owned wardrobe items that fit the request."
    )
    compatibility: Optional[CompatibilityDetails] = None
    confidence: ConfidenceMetrics
    search_requirements: Agent2SearchRequirement = Field(
        ..., description="Search brief for Agent 2 (also nested under agent2_handoff)."
    )
    agent2_handoff: Optional[Agent2HandoffPayload] = Field(
        None, description="Full structured handoff package for Agent 2."
    )

    @model_validator(mode="after")
    def _fill_agent2_handoff(self):
        if self.agent2_handoff is not None:
            return self
        avail_cats = list(self.outfit_requirements.available_categories)
        missing = list(self.outfit_requirements.missing_categories)
        items: List[Agent2AvailableItem] = []
        seen = set()
        for w in self.wardrobe:
            cat = w.category.lower()
            if cat in {c.lower() for c in avail_cats} and cat not in seen:
                seen.add(cat)
                items.append(
                    Agent2AvailableItem(
                        wardrobe_id=w.wardrobe_id,
                        category=w.category,
                        type=w.type,
                        colour=w.colour,
                    )
                )
        self.agent2_handoff = Agent2HandoffPayload(
            request_id=self.request_id,
            user_requirements=self.user_requirements,
            wardrobe_status=Agent2WardrobeStatus(
                available_categories=avail_cats,
                missing_categories=missing,
            ),
            available_items=items,
            search_requirements=self.search_requirements,
        )
        return self


# ---------------------------------------------------------------------------
# Input Contract for Agent 1 inter-service analysis
# ---------------------------------------------------------------------------

class Agent1AnalysisRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Optional request ID; generated if omitted.")
    user_id: Optional[int] = Field(None, description="Target user ID for wardrobe lookup.")
    query_text: str = Field(..., description="Natural-language fashion request.")
    occasion: Optional[str] = Field(None, description="Explicit occasion override if provided.")
    style: Optional[str] = Field(None, description="Explicit style override if provided.")
    colour_preference: Optional[str] = Field(None, description="Explicit color preference override.")
    budget: Optional[float] = Field(None, description="Explicit budget override.")
