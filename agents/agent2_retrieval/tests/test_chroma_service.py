"""
Unit and integration tests for ChromaService in Agent 2.
Verifies client/collection initialization, collection count, semantic similarity search,
top_k validation, empty input handling, metadata filtering, and database non-destructive integrity.
"""

import sys
from pathlib import Path

agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

import pytest
from app.services.chroma_service import ChromaService, get_chroma_service
from app.services.embedding_service import get_embedding_service


def test_chroma_service_initialization():
    service = ChromaService()
    assert service.collection_name == "fashion_products"
    assert service.collection is not None


def test_collection_count():
    service = ChromaService()
    count = service.get_count()
    assert isinstance(count, int)
    # Production collection contains 43,070 items
    assert count == 43070
    assert service.count() == 43070


def test_semantic_search_with_query_embedding():
    service = ChromaService()
    embed_svc = get_embedding_service()
    q_emb = embed_svc.generate_embedding("beige suede loafers")

    results = service.search_similar(query_embedding=q_emb, top_k=5)
    assert isinstance(results, list)
    assert len(results) == 5
    for item in results:
        assert "product_id" in item
        assert "similarity" in item
        assert "distance" in item
        assert "metadata" in item
        assert 0.0 <= item["similarity"] <= 1.0


def test_semantic_search_with_query_text():
    service = ChromaService()
    results = service.search_similar(query_text="linen shirt", top_k=3)
    assert isinstance(results, list)
    assert len(results) == 3


def test_top_k_validation_and_clamping():
    service = ChromaService()
    embed_svc = get_embedding_service()
    q_emb = embed_svc.generate_embedding("casual top")

    # Invalid top_k (< 1) should fallback to default 10
    res_neg = service.search_similar(query_embedding=q_emb, top_k=-5)
    assert len(res_neg) == 10

    # Large top_k should be clamped safely to max or collection count
    res_large = service.search_similar(query_embedding=q_emb, top_k=50000)
    assert len(res_large) <= 43070


def test_empty_and_invalid_query_handling():
    service = ChromaService()

    # None embedding & None query text -> empty results
    assert service.search_similar(query_embedding=None, query_text=None) == []
    # Empty string -> empty results
    assert service.search_similar(query_text="") == []
    # Empty embedding list -> empty results
    assert service.search_similar(query_embedding=[]) == []


def test_metadata_filtering():
    service = ChromaService()
    embed_svc = get_embedding_service()
    q_emb = embed_svc.generate_embedding("black dress")

    # Filter by category
    results = service.search_similar(
        query_embedding=q_emb,
        top_k=5,
        where_filter={"category": "footwear"}
    )
    assert isinstance(results, list)
    for r in results:
        if r["metadata"]:
            assert r["metadata"].get("category") == "footwear"


def test_singleton_getter():
    svc1 = get_chroma_service()
    svc2 = get_chroma_service()
    assert svc1 is svc2


def test_collection_integrity_non_destructive():
    """Verify that search operations do not alter collection count."""
    service = ChromaService()
    initial_count = service.get_count()
    assert initial_count == 43070

    # Perform multiple queries
    service.search_similar(query_text="white sneakers", top_k=10)
    service.search_similar(query_text="formal suit", top_k=5)

    final_count = service.get_count()
    assert final_count == initial_count == 43070
