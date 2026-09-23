from pydantic import BaseModel, Field
from typing import List, Optional

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, description="The search query text")
    missing_items: Optional[List[str]] = Field(default=None, description="List of items missing from the outfit")
    category: Optional[str] = Field(default=None, description="Target product category")
    colour: Optional[str] = Field(default=None, description="Target product colour")
    style: Optional[str] = Field(default=None, description="Target product style")
    occasion: Optional[str] = Field(default=None, description="Occasion for the outfit")
    budget: Optional[float] = Field(default=None, ge=0, description="Maximum budget in local currency")
    gender: Optional[str] = Field(default=None, description="Target gender for the product")
    top_k: Optional[int] = Field(default=10, ge=1, le=100, description="Number of results to return")

class SearchResult(BaseModel):
    product_id: str
    product_name: str
    category: Optional[str]
    colour: Optional[str]
    price: Optional[float]
    brand: Optional[str]
    image_url: Optional[str]
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
