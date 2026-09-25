"""
UsageRecord ORM model — per-user monthly recommendation quota and tier.
Lives in the shared system database (table: budget_usage_records).
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.db import Base


class UsageRecord(Base):
    """One row per user per calendar month."""

    __tablename__ = "budget_usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    year_month = Column(String(7), nullable=False, index=True)  # "2026-09"
    recommendation_count = Column(Integer, default=0, nullable=False)
    tier = Column(String(16), default="free", nullable=False)  # "free" | "premium"
    upgraded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<UsageRecord user={self.user_id} month={self.year_month} "
            f"count={self.recommendation_count} tier={self.tier}>"
        )
