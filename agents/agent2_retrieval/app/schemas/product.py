from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    product_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    colour: Optional[str] = None
    material: Optional[str] = None
    style: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    store: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    availability: Optional[bool] = None

class ProductCreate(ProductBase):
    product_id: str

class Product(ProductBase):
    product_id: str
    created_at: datetime

    class Config:
        from_attributes = True
