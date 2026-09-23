"""
Schemas package initialization.
"""

from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.schemas.wardrobe import (
    ClothingAttributesDetected,
    ImageAnalysisDraft,
    WardrobeItemCreate,
    WardrobeItemUpdate,
    WardrobeItemResponse,
)
from app.schemas.analysis import (
    FashionRequestInput,
    FashionAnalysisResponse,
)

__all__ = [
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenResponse",
    "UserProfileResponse",
    "ClothingAttributesDetected",
    "ImageAnalysisDraft",
    "WardrobeItemCreate",
    "WardrobeItemUpdate",
    "WardrobeItemResponse",
    "FashionRequestInput",
    "FashionAnalysisResponse",
]
