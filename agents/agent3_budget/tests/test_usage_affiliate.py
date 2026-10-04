"""Usage-quota and affiliate-tracking unit tests (USD, shared-DB tables)."""

from app.services.affiliate_service import get_affiliate_service
from app.services.usage_service import get_usage_service


# ── Usage / subscription ────────────────────────────────────────────────────

def test_new_user_starts_at_zero(db):
    stats = get_usage_service().get_usage_stats(db, "u1")
    assert stats["recommendations_used"] == 0
    assert stats["tier"] == "free"


def test_free_tier_blocks_at_limit(db):
    svc = get_usage_service()
    for _ in range(3):
        allowed, _, _, _ = svc.check_quota(db, "u2")
        assert allowed
        svc.increment_usage(db, "u2")
    allowed, msg, used, limit = svc.check_quota(db, "u2")
    assert not allowed and used == 3 and limit == 3
    assert "Free tier limit" in msg


def test_premium_upgrade_and_downgrade(db):
    svc = get_usage_service()
    svc.upgrade_to_premium(db, "u3")
    allowed, msg, _, limit = svc.check_quota(db, "u3")
    assert allowed and limit == -1 and "Premium" in msg
    svc.downgrade_to_free(db, "u3")
    _, _, _, limit = svc.check_quota(db, "u3")
    assert limit == 3


def test_usage_stats_premium_price_is_usd(db):
    stats = get_usage_service().get_usage_stats(db, "u4")
    assert stats["premium_price_usd"] > 0
    assert "premium_price_lkr" not in stats


def test_idempotent_record_creation(db):
    svc = get_usage_service()
    a = svc.get_or_create_record(db, "u5")
    b = svc.get_or_create_record(db, "u5")
    assert a.id == b.id


# ── Affiliate ────────────────────────────────────────────────────────────────

def test_record_click_persists_usd(db):
    click = get_affiliate_service().record_click(
        db, product_id="P1", product_name="Dress", product_url="https://www.amazon.com/dp/P1",
        store="Amazon", category="dress", price_usd=40.0, user_id="u6", request_id="REQ-6",
        client_ip="203.0.113.9",
    )
    assert click.id is not None
    assert click.price_usd == 40.0


def test_commission_math(db):
    click = get_affiliate_service().record_click(
        db, product_id="P2", product_name=None, product_url=None, store=None,
        category=None, price_usd=40.0,
    )
    assert click.estimated_commission_usd == round(40.0 * 0.05, 4)


def test_no_commission_without_price(db):
    click = get_affiliate_service().record_click(
        db, product_id="P3", product_name=None, product_url=None, store=None,
        category=None, price_usd=None,
    )
    assert click.estimated_commission_usd is None


def test_ip_is_hashed_not_stored(db):
    click = get_affiliate_service().record_click(
        db, product_id="P4", product_name=None, product_url=None, store=None,
        category=None, price_usd=10.0, client_ip="198.51.100.7",
    )
    assert click.ip_hash and "198.51.100.7" not in click.ip_hash
    assert len(click.ip_hash) == 16


def test_tracked_url_and_history(db):
    svc = get_affiliate_service()
    svc.record_click(
        db, product_id="P5", product_name="Shoe", product_url="https://www.amazon.com/dp/P5",
        store="Amazon", category="footwear", price_usd=20.0, user_id="u7",
    )
    tracked = svc.build_tracked_url("P5", "https://www.amazon.com/dp/P5")
    assert "/budget/affiliate/redirect/P5" in tracked
    history = svc.get_user_clicks(db, "u7")
    assert history and history[0]["product_id"] == "P5"
    assert "price_usd" in history[0]


def test_clear_user_clicks_only_touches_that_user(db):
    svc = get_affiliate_service()
    for uid in ("ca", "ca", "cb"):
        svc.record_click(
            db, product_id=f"P-{uid}", product_name=None, product_url=None,
            store=None, category=None, price_usd=None, user_id=uid,
        )
    assert svc.clear_user_clicks(db, "ca") == 2
    assert svc.get_user_clicks(db, "ca") == []
    assert len(svc.get_user_clicks(db, "cb")) == 1


def test_affiliate_history_delete_route(client, user_headers):
    tracked = client.post(
        "/budget/affiliate/track-click",
        json={"product_id": "PDEL", "product_url": "https://www.amazon.com/dp/PDEL"},
        headers=user_headers,
    )
    assert tracked.status_code == 200
    assert client.get("/budget/affiliate/history/42", headers=user_headers).json()["clicks"]

    cleared = client.delete("/budget/affiliate/history/42", headers=user_headers)
    assert cleared.status_code == 200
    assert cleared.json()["cleared"] == 1
    assert client.get("/budget/affiliate/history/42", headers=user_headers).json()["clicks"] == []


def test_affiliate_history_delete_requires_auth(client):
    assert client.delete("/budget/affiliate/history/42").status_code == 401


def test_click_stats_aggregation(db):
    svc = get_affiliate_service()
    for i in range(3):
        svc.record_click(
            db, product_id=f"PS{i}", product_name=None, product_url=None,
            store="Amazon", category="dress", price_usd=10.0,
        )
    stats = svc.get_click_stats(db)
    assert stats["total_clicks"] >= 3
    assert stats["total_estimated_commission_usd"] > 0
    assert stats["by_store"]["Amazon"]["clicks"] >= 3
