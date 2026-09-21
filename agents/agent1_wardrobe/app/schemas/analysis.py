"""
Fashion request and analysis view schemas.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    CompatibilityDetails,
    ConfidenceMetrics,
    Agent2SearchRequirement,
    Agent1OutputContract,
)


class FashionRequestInput(BaseModel):
    query_text: str = Field(..., min_length=3, description="User's natural language fashion request.")
    occasion: Optional[str] = Field(None, description="Optional explicit occasion override.")
    style: Optional[str] = Field(None, description="Optional explicit style override.")
    colour_preference: Optional[str] = Field(None, description="Optional explicit color preference.")
    budget: Optional[float] = Field(None, gt=0, description="Optional explicit budget ceiling in LKR.")


class FashionAnalysisResponse(BaseModel):
    request_id: str
    timestamp: datetime
    input_text: str
    user_requirements: UserRequirements
    available_wardrobe: List[WardrobeSummaryItem]
    outfit_requirements: OutfitRequirements
    compatible_items: List[WardrobeSummaryItem]
    compatibility: Optional[CompatibilityDetails]
    confidence: ConfidenceMetrics
    search_requirements: Agent2SearchRequirement
    raw_agent1_contract: Agent1OutputContract
