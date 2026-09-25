"""
Subscription & usage quota service.

  Free tier  — FREE_TIER_MONTHLY_LIMIT recommendations per calendar month
  Premium    — unlimited

Quota rows live in the shared database (table budget_usage_records).
"""

import logging
from datetime import datetime
from typing import Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.usage_record import UsageRecord

logger = logging.getLogger("budget_usage")
settings = get_settings()


class UsageService:
    """Per-user monthly recommendation quota and tier management."""

    def _current_year_month(self) -> str:
        return datetime.utcnow().strftime("%Y-%m")

    def get_or_create_record(self, db: Session, user_id: str) -> UsageRecord:
        ym = self._current_year_month()
        record = (
            db.query(UsageRecord)
            .filter(UsageRecord.user_id == user_id, UsageRecord.year_month == ym)
            .first()
        )
        if not record:
            record = UsageRecord(
                user_id=user_id, year_month=ym, recommendation_count=0, tier="free"
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        return record

    def check_quota(self, db: Session, user_id: str) -> Tuple[bool, str, int, int]:
        """Returns (allowed, message, used, limit). Premium limit is -1."""
        record = self.get_or_create_record(db, user_id)
        if record.tier == "premium":
            return True, "Premium — unlimited recommendations.", record.recommendation_count, -1

        limit = settings.FREE_TIER_MONTHLY_LIMIT
        used = record.recommendation_count
        if used >= limit:
            return (
                False,
                f"Free tier limit reached ({used}/{limit} recommendations this month). "
                "Upgrade to Premium for unlimited access.",
                used,
                limit,
            )
        return True, f"Free tier: {used + 1}/{limit} used this month.", used, limit

    def increment_usage(self, db: Session, user_id: str) -> UsageRecord:
        record = self.get_or_create_record(db, user_id)
        record.recommendation_count += 1
        record.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(record)
        logger.info(
            f"Usage incremented: user={user_id} count={record.recommendation_count} tier={record.tier}"
        )
        return record

    def upgrade_to_premium(self, db: Session, user_id: str) -> UsageRecord:
        record = self.get_or_create_record(db, user_id)
        record.tier = "premium"
        record.upgraded_at = datetime.utcnow()
        db.commit()
        db.refresh(record)
        logger.info(f"User {user_id} upgraded to premium.")
        return record

    def downgrade_to_free(self, db: Session, user_id: str) -> UsageRecord:
        record = self.get_or_create_record(db, user_id)
        record.tier = "free"
        db.commit()
        db.refresh(record)
        return record

    def get_usage_stats(self, db: Session, user_id: str) -> dict:
        record = self.get_or_create_record(db, user_id)
        limit = -1 if record.tier == "premium" else settings.FREE_TIER_MONTHLY_LIMIT
        remaining = max(0, limit - record.recommendation_count) if limit != -1 else -1
        return {
            "user_id": user_id,
            "month": record.year_month,
            "tier": record.tier,
            "recommendations_used": record.recommendation_count,
            "monthly_limit": limit,
            "recommendations_remaining": remaining,
            "upgraded_at": record.upgraded_at.isoformat() if record.upgraded_at else None,
            "premium_price_usd": settings.PREMIUM_MONTHLY_PRICE_USD,
            "premium_benefits": [
                "Unlimited recommendations",
                "Wardrobe tracking",
                "Advanced style analysis",
                "Shopping optimisation",
                "Personalised fashion history",
            ],
        }


_usage_service = UsageService()


def get_usage_service() -> UsageService:
    return _usage_service
