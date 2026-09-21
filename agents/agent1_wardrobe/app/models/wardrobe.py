"""
WardrobeItem ORM model.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.database import Base


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id = Column(Integer, primary_key=True, index=True)
    wardrobe_code = Column(String(50), index=True, nullable=False)  # e.g. 'W001'
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    image_path = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False, index=True)  # top, bottom, shoes, etc.
    type = Column(String(50), nullable=False)                  # blouse, jeans, loafers, etc.
    colour = Column(String(50), nullable=False, index=True)    # black, blue, beige, etc.
    secondary_colour = Column(String(50), nullable=True)
    pattern = Column(String(50), default="solid", nullable=False)
    style = Column(String(50), default="casual", nullable=False, index=True)
    sleeve_type = Column(String(50), nullable=True)
    formality = Column(Float, default=0.5, nullable=False)
    material = Column(String(100), nullable=True)
    
    confidence = Column(Float, default=1.0, nullable=False)
    attributes_confirmed = Column(Boolean, default=False, nullable=False)
    embedding = Column(Text, nullable=True)  # Serialized vector representation
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="wardrobe_items")
