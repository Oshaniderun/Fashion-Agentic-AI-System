"""
FASHORA Shared ORM Models.
All agents import from here — one source of truth for shared tables.

Shared tables (used by all agents):
  - User             → authentication, ownership
  - AnalysisRecord   → Agent 1 output history, consumable by Agent 2/3/4

Agent-local tables live inside each agent's own app/models/:
  - WardrobeItem     → Agent 1
  - Product          → Agent 2
  - PurchasePlan     → Agent 3
  - Recommendation   → Agent 4
"""

from shared.models.database import Base, get_shared_db, init_shared_db
from shared.models.user import User
from shared.models.analysis_record import AnalysisRecord

__all__ = [
    "Base",
    "get_shared_db",
    "init_shared_db",
    "User",
    "AnalysisRecord",
]
