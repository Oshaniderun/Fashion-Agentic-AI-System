"""
Affiliate tracking service.

Records product-link clicks, estimates commission at the configured rate,
and builds tracked redirect URLs through this service.

Security fix over the original team build: the redirect destination is
validated against an HTTPS + retailer-domain allowlist, closing the
open-redirect vector of the raw ?destination= passthrough.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.affiliate_click import AffiliateClick

logger = logging.getLogger("budget_affiliate")
settings = get_settings()

# Allowed redirect target domains (subdomains permitted on suffix match).
AFFILIATE_ALLOWED_DOMAINS = (
    "amazon.com",
    "amazon.in",
    "amazon.co.uk",
    "amzn.to",
    "flipkart.com",
    "myntra.com",
)


def is_allowed_destination(url: Optional[str]) -> bool:
    """True only for https URLs whose host matches an allowlisted retailer domain."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(
        host == d or host.endswith("." + d) for d in AFFILIATE_ALLOWED_DOMAINS
    )


class AffiliateService:
    """Records product link clicks and computes estimated commissions."""

    def record_click(
        self,
        db: Session,
        product_id: str,
        product_name: Optional[str],
        product_url: Optional[str],
        store: Optional[str],
        category: Optional[str],
        price_usd: Optional[float],
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> AffiliateClick:
        """Persist one affiliate click and return the record."""
        commission = None
        if price_usd and price_usd > 0:
            commission = round(price_usd * settings.AFFILIATE_COMMISSION_RATE, 4)

        ip_hash = None
        if client_ip:
            ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

        click = AffiliateClick(
            user_id=user_id,
            request_id=request_id,
            product_id=product_id,
            product_name=(product_name or "")[:500] or None,
            store=store,
            product_url=product_url,
            category=category,
            price_usd=price_usd,
            commission_rate=settings.AFFILIATE_COMMISSION_RATE,
            estimated_commission_usd=commission,
            clicked_at=datetime.utcnow(),
            ip_hash=ip_hash,
        )
        db.add(click)
        db.commit()
        db.refresh(click)
        logger.info(
            f"Affiliate click recorded: product={product_id} store={store} "
            f"commission=USD {commission or 0:.2f}"
        )
        return click

    def build_tracked_url(self, product_id: str, original_url: Optional[str]) -> str:
        """Wrap a product URL in a tracked redirect through this service."""
        base = f"{settings.AFFILIATE_BASE_URL.rstrip('/')}/budget/affiliate/redirect/{product_id}"
        if not original_url:
            return base
        return f"{base}?destination={original_url}"

    def get_click_stats(self, db: Session, days: int = 30) -> dict:
        """Total clicks, estimated commission and per-store/category breakdown."""
        since = datetime.utcnow() - timedelta(days=days)
        rows = db.query(AffiliateClick).filter(AffiliateClick.clicked_at >= since).all()

        total_clicks = len(rows)
        total_commission = sum(r.estimated_commission_usd or 0 for r in rows)
        by_store: dict = {}
        by_category: dict = {}

        for r in rows:
            s = r.store or "Unknown"
            by_store.setdefault(s, {"clicks": 0, "commission_usd": 0})
            by_store[s]["clicks"] += 1
            by_store[s]["commission_usd"] += round(r.estimated_commission_usd or 0, 4)

            c = r.category or "Unknown"
            by_category.setdefault(c, {"clicks": 0})
            by_category[c]["clicks"] += 1

        return {
            "period_days": days,
            "total_clicks": total_clicks,
            "total_estimated_commission_usd": round(total_commission, 4),
            "commission_rate": settings.AFFILIATE_COMMISSION_RATE,
            "by_store": by_store,
            "by_category": by_category,
        }

    def get_user_clicks(self, db: Session, user_id: str, limit: int = 20) -> List[dict]:
        """A user's recent clicks."""
        clicks = (
            db.query(AffiliateClick)
            .filter(AffiliateClick.user_id == user_id)
            .order_by(AffiliateClick.clicked_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "product_id": c.product_id,
                "product_name": c.product_name,
                "product_url": c.product_url,
                "store": c.store,
                "category": c.category,
                "price_usd": c.price_usd,
                "estimated_commission_usd": c.estimated_commission_usd,
                "clicked_at": c.clicked_at.isoformat(),
            }
            for c in clicks
        ]


_affiliate_service = AffiliateService()


def get_affiliate_service() -> AffiliateService:
    return _affiliate_service
