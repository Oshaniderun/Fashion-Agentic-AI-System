"""
Agent 1 models package.

Shared tables (User, AnalysisRecord) are sourced from shared/models/.
Agent-local table (WardrobeItem) is defined here and registers on the same shared Base.
"""

from app.models.database import Base, engine, SessionLocal, get_db, init_db
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.models.analysis import AnalysisRecord

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "User",
    "WardrobeItem",
    "AnalysisRecord",
]
