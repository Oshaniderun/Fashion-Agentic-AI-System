from sqlalchemy import Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    product_id = Column(String, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    category = Column(String, index=True)
    subcategory = Column(String, index=True)
    brand = Column(String, index=True)
    price = Column(Float)
    currency = Column(String)
    colour = Column(String, index=True)
    material = Column(String)
    style = Column(String, index=True)
    size = Column(String)
    description = Column(Text)
    store = Column(String)
    image_url = Column(String)
    product_url = Column(String)
    availability = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
