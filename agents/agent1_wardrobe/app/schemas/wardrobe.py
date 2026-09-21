"""
Wardrobe and clothing item schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ClothingAttributesDetected(BaseModel):
    category: str = Field(..., description="Detected category, e.g. 'top', 'bottom', 'shoes'.")
    type: str = Field(..., description="Garment type, e.g. 'blouse', 'jeans', 'loafers'.")
    colour: str = Field(..., description="Primary detected color.")
    secondary_colour: Optional[str] = None
    pattern: str = Field("solid", description="Detected pattern: solid, striped, floral, etc.")
    style: str = Field("casual", description="Inferred style category.")
    sleeve_type: Optional[str] = None
    formality: float = Field(0.5, ge=0.0, le=1.0, description="Formality index (0.0=casual, 1.0=formal).")
    material: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    color_palette: List[str] = Field(default_factory=list, description="Top extracted hex/rgb colors.")


class ImageAnalysisDraft(BaseModel):
    draft_id: str
    image_url: str
    detected_attributes: ClothingAttributesDetected
    is_confirmed: bool = False


class WardrobeItemCreate(BaseModel):
    image_path: str
    category: str
    type: str
    colour: str
    secondary_colour: Optional[str] = None
    pattern: str = "solid"
    style: str = "casual"
    sleeve_type: Optional[str] = None
    formality: float = Field(0.5, ge=0.0, le=1.0)
    material: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    attributes_confirmed: bool = True


class WardrobeItemUpdate(BaseModel):
    category: Optional[str] = None
    type: Optional[str] = None
    colour: Optional[str] = None
    secondary_colour: Optional[str] = None
    pattern: Optional[str] = None
    style: Optional[str] = None
    sleeve_type: Optional[str] = None
    formality: Optional[float] = Field(None, ge=0.0, le=1.0)
    material: Optional[str] = None


class WardrobeItemResponse(BaseModel):
    id: int
    wardrobe_code: str
    user_id: int
    image_url: str
    category: str
    type: str
    colour: str
    secondary_colour: Optional[str]
    pattern: str
    style: str
    sleeve_type: Optional[str]
    formality: float
    material: Optional[str]
    confidence: float
    attributes_confirmed: bool
    created_at: datetime
    updated_at: datetime
