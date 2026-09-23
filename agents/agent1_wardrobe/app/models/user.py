"""
User model — Agent 1 re-export from shared layer.
Import path stays the same for Agent 1 internals: from app.models.user import User
"""

from shared.models.user import User  # noqa: F401

__all__ = ["User"]
