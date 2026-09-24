"""
Unit and integration tests for BM25Service in Agent 2.
Verifies service initialization, loading of existing bm25_index.pkl (43,070 docs),
keyword search, score validity, top_k clamping, empty/invalid input safety,
index caching/reuse, and non-destructive read operations.
"""

import sys
from pathlib import Path

agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

import pytest
from app.services.bm25_service import BM25Service, get_bm25_service, tokenize


def test_bm25_service_initialization_and_count():
    service = BM25Service()
    assert service.bm25 is not None
    assert service.get_count() == 43070
    assert service.count() == 43070
    assert len(service.product_ids) == 43070


def test_tokenization_consistency():
    tokens = tokenize("Beige Suede Loafers! Women's $4000")
    assert "beige" in tokens
    assert "suede" in tokens
    assert "loafers" in tokens
    assert "4000" in tokens


def test_keyword_search_returns_valid_results():
    service = BM25Service()
    results = service.search(query="beige suede loafers", top_k=5)
    assert isinstance(results, list)
    assert len(results) == 5
    for item in results:
        assert "product_id" in item
        assert "bm25_score" in item
        assert 0.0 <= item["bm25_score"] <= 1.0

    # Scores should be sorted descending
    scores = [r["bm25_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_top_k_handling():
    service = BM25Service()

    # top_k <= 0 should safely return empty list
    assert service.search(query="linen shirt", top_k=0) == []
    assert service.search(query="linen shirt", top_k=-5) == []

    # normal top_k
    res_3 = service.search(query="linen shirt", top_k=3)
    assert len(res_3) == 3

    # top_k larger than document count
    res_large = service.search(query="shirt", top_k=50000)
    assert len(res_large) <= 43070


def test_empty_and_invalid_query_handling():
    service = BM25Service()

    # Empty string
    assert service.search(query="") == []
    # Whitespace only
    assert service.search(query="   \t\n  ") == []
    # None or non-string
    assert service.search(query=None) == []  # type: ignore
    assert service.search(query=12345) == []  # type: ignore


def test_repeated_searches_reuse_loaded_index():
    svc1 = get_bm25_service()
    svc2 = get_bm25_service()
    assert svc1 is svc2

    # Multiple searches on same service
    r1 = svc1.search(query="cotton dress", top_k=2)
    r2 = svc1.search(query="silk scarf", top_k=2)
    assert len(r1) == 2
    assert len(r2) == 2


def test_index_integrity_non_destructive():
    """Verify that search operations do not modify index document count or file."""
    service = BM25Service()
    initial_count = service.get_count()
    assert initial_count == 43070

    index_mtime = service.index_path.stat().st_mtime

    # Perform multiple queries
    service.search(query="black dress shoes", top_k=10)
    service.search(query="formal blazer", top_k=5)

    final_count = service.get_count()
    assert final_count == initial_count == 43070
    assert service.index_path.stat().st_mtime == index_mtime


def test_category_filtering():
    service = BM25Service()
    results = service.search(query="shirt", top_k=5, category="top")
    assert len(results) > 0
    for r in results:
        assert "metadata" in r
        assert r["metadata"].get("category") == "top"


def test_max_price_filtering():
    service = BM25Service()
    max_price = 3000.0
    results = service.search(query="dress", top_k=10, max_price=max_price)
    assert len(results) > 0
    for r in results:
        price = r.get("metadata", {}).get("price")
        if price is not None:
            assert float(price) <= max_price


def test_excluded_ids_filtering():
    service = BM25Service()
    initial_results = service.search(query="loafers", top_k=5)
    assert len(initial_results) > 0
    excluded_id = initial_results[0]["product_id"]

    filtered_results = service.search(query="loafers", top_k=5, excluded_ids=[excluded_id])
    returned_ids = [r["product_id"] for r in filtered_results]
    assert excluded_id not in returned_ids

