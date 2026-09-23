"""
Agent 1 database session — thin wrapper around the shared database module.

All session/engine management is in shared/models/database.py.
This module exists so Agent 1's internal imports continue to work
unchanged (from app.models.database import get_db, init_db, Base, etc.)
while the actual implementation is shared.
"""

# Re-export everything Agent 1 internally uses from the shared layer.
from shared.models.database import (  # noqa: F401
    Base,
    engine,
    SessionLocal,
    get_shared_db as get_db,
    init_shared_db as init_db,
)

__all__ = ["Base", "engine", "SessionLocal", "get_db", "init_db"]
