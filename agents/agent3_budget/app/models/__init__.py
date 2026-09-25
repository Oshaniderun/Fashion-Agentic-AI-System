"""
ORM models for the Budget & Purchase Planning service.

Tables live in the SHARED system database (same PostgreSQL DATABASE_URL as
Agents 1 & 2) under budget_* names. See app/core/db.py for why this service
uses its own declarative Base.
"""

from app.core.db import Base
from app.models.usage_record import UsageRecord  # noqa: E402,F401
from app.models.affiliate_click import AffiliateClick  # noqa: E402,F401

__all__ = ["Base", "UsageRecord", "AffiliateClick"]
