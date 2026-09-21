"""
Agent inter-service communication schemas.
Re-exports the shared single-source-of-truth contract models.
"""

from shared.schemas.agent1_schemas import (
    UserRequirements,
    WardrobeSummaryItem,
    OutfitRequirements,
    CompatibilityDetails,
    ConfidenceMetrics,
    Agent2SearchRequirement,
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
    "Agent1OutputContract",
    "Agent1AnalysisRequest",
]
