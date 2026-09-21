"""
Shared Pydantic models across FASHORA agents.
Source of truth for request/response shapes.
"""

from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    CompatibilityDetails,
    ConfidenceMetrics,
    Agent2SearchRequirement,
    Agent2HandoffPayload,
    Agent1OutputContract,
    Agent1AnalysisRequest,
)

__all__ = [
    "UserRequirements",
    "WardrobeSummaryItem",
    "OutfitRequirements",
    "CompatibilityDetails",
    "ConfidenceMetrics",
    "Agent2SearchRequirement",
    "Agent2HandoffPayload",
    "Agent1OutputContract",
    "Agent1AnalysisRequest",
]
