"""
User ORM model — shared across all FASHORA agents.

Owns: authentication, identity, and cross-agent ownership linking.
All agent-local tables (wardrobe_items, products, etc.) reference users.id.

IMPORTANT: Relationships back-populated from agent-local models are declared
in those models (e.g. WardrobeItem.user). We do NOT import agent-local models
here to avoid circular dependencies. Use lazy 'dynamic' or string-based back_populates
only when needed from within the shared model.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from shared.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships — declared here so SQLAlchemy resolves them when all models are loaded.
    # Each agent's model file sets the matching back_populates on its side.
    wardrobe_items = relationship(
        "WardrobeItem",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    analysis_records = relationship(
        "AnalysisRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
