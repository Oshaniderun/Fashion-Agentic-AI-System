"""
Agent 1 — Style & Wardrobe Intelligence
Shared Pydantic contracts between Agent 1 and downstream agents (Agents 2, 3, 4, Orchestrator).
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from shared.constants import (
    ProductCategory,
    OccasionType,
    StyleType,
    ColorCategory,
    PatternType
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


class Agent2SearchRequirement(BaseModel):
    """
    Prepared handoff payload specifically structured for Agent 2 (Information Retrieval).
    """
    missing_categories: List[str] = Field(..., description="Categories Agent 2 needs to query.")
    style: List[str] = Field(default_factory=list, description="Target styles to filter.")
    colour: List[str] = Field(default_factory=list, description="Target colors.")
    occasion: Optional[str] = Field(None, description="Event context.")
    budget_remaining: Optional[float] = Field(None, description="Maximum budget allocated.")
    query_text: Optional[str] = Field(None, description="Synthesized expanded query for BM25 / vector search.")


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
        ..., description="Clean handoff package for Agent 2 retrieval."
    )


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
