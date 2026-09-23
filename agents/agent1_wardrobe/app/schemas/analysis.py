"""
Fashion request and analysis view schemas.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from datetime import datetime

from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    CompatibilityDetails,
    ConfidenceMetrics,
    Agent2SearchRequirement,
    Agent2HandoffPayload,
    Agent2WardrobeStatus,
    Agent2AvailableItem,
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
    agent2_handoff: Optional[Agent2HandoffPayload] = None
    raw_agent1_contract: Agent1OutputContract

    @model_validator(mode="after")
    def _fill_agent2_handoff(self):
        if self.agent2_handoff is not None:
            return self
        avail_cats = list(self.outfit_requirements.available_categories)
        missing = list(self.outfit_requirements.missing_categories)
        items: List[Agent2AvailableItem] = []
        seen = set()
        for w in self.available_wardrobe:
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
