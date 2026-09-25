"""
AffiliateClick ORM model — every recommended-product link click, used for
commission estimation. Lives in the shared system database
(table: budget_affiliate_clicks). All money columns are USD.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.core.db import Base


class AffiliateClick(Base):
    """One row per affiliate link click."""

    __tablename__ = "budget_affiliate_clicks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True, index=True)
    product_id = Column(String(255), nullable=False, index=True)
    product_name = Column(String(512), nullable=True)
    store = Column(String(255), nullable=True)
    product_url = Column(Text, nullable=True)
    category = Column(String(128), nullable=True)
    price_usd = Column(Float, nullable=True)
    commission_rate = Column(Float, default=0.05)
    estimated_commission_usd = Column(Float, nullable=True)
    clicked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_hash = Column(String(64), nullable=True)  # hashed client IP, never raw

    def __repr__(self):
        return f"<AffiliateClick product={self.product_id} store={self.store} user={self.user_id}>"
