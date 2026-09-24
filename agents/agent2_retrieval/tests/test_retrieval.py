"""
Functional and integration tests for Agent 2 Information Retrieval components:
BM25, Semantic search, Hybrid candidate retrieval, Ranking service,
and Decision logic relaxation ladder.
"""

import pytest
import os
import sys
from pathlib import Path

# Setup paths
agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

from shared.constants import ProductCategory
from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalStatus
from app.services.bm25_service import BM25Service
from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService
from app.services.ranking_service import RankingService
from app.services.retrieval_service import RetrievalService, get_retrieval_service
from app.decision_logic import resolve_retrieval

SAMPLE_PRODUCTS = [
    {
        "product_id": "P_TOP_1",
        "product_name": "Classic White Linen Shirt",
        "category": "top",
        "colour": "White",
        "style": "casual",
        "price": 3000.0,
        "availability": True,
        "description": "Breathable summer linen shirt with classic button collar."
    },
    {
        "product_id": "P_TOP_2",
        "product_name": "Navy Blue Oxford Formal Shirt",
        "category": "top",
        "colour": "Navy Blue",
        "style": "formal",
        "price": 4500.0,
        "availability": True,
        "description": "Crisp tailored oxford shirt in deep navy blue."
    },
    {
        "product_id": "P_SHOE_1",
        "product_name": "Beige Suede Smart Loafers",
        "category": ProductCategory.SHOES.value,
        "colour": "Beige",
        "style": "smart casual",
        "price": 4800.0,
        "availability": True,
        "description": "Comfortable pointed toe slip-on loafer in soft beige suede."
    },
    {
        "product_id": "P_SHOE_2",
        "product_name": "Black Leather Formal Oxfords",
        "category": ProductCategory.SHOES.value,
        "colour": "Black",
        "style": "formal",
        "price": 6000.0,
        "availability": True,
        "description": "Glossy dress shoes for black tie events."
    },
    {
        "product_id": "P_SHOE_3",
        "product_name": "Brown Brogue Shoes",
        "category": ProductCategory.SHOES.value,
        "colour": "Brown",
        "style": "vintage",
        "price": 5400.0,
        "availability": True,
        "description": "Wingtip brown leather shoes."
    }
]


def test_bm25_service_ranking():
    """Verify BM25Service keyword search on precomputed index."""
    bm25 = BM25Service()
    results = bm25.search(query="beige suede loafers", top_k=5)
    assert len(results) > 0
    assert results[0]["bm25_score"] > 0
    assert "product_id" in results[0]
    scores = [r["bm25_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_ranking_formula():
    """Unit test for RankingService formula and ScoreBreakdown computation."""
    score, breakdown = RankingService.compute_score(
        bm25_score=0.9,
        dense_similarity=0.8,
        product_price=4000.0,
        max_price=5000.0,
        product_colour="Beige",
        requested_colour="Beige",
        product_style="smart casual",
        requested_style="smart casual",
        is_available=True
    )
    assert 0.0 <= score <= 1.0
    assert breakdown.colour_match == 1.0
    assert breakdown.style_match == 1.0
    assert breakdown.availability == 1.0
    assert breakdown.semantic_similarity == round(0.5 * 0.9 + 0.5 * 0.8, 4)


def test_hybrid_retrieval_candidate_union(monkeypatch):
    """Verify search combines candidates from BM25 and Chroma and ranks them."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    # BM25 returns P_SHOE_1 and P_SHOE_3
    monkeypatch.setattr(
        service.bm25_service,
        "search",
        lambda **kwargs: [
            {"product_id": "P_SHOE_1", "bm25_score": 0.85},
            {"product_id": "P_SHOE_3", "bm25_score": 0.50},
        ]
    )
    # Mock embedding generation to avoid external model calls
    monkeypatch.setattr(
        service.embedding_service,
        "generate_embedding",
        lambda query: [0.1] * 384
    )
    # Chroma returns P_SHOE_2 and P_SHOE_3
    monkeypatch.setattr(
        service.chroma_service,
        "search_similar",
        lambda **kwargs: [
            {"product_id": "P_SHOE_2", "similarity": 0.90},
            {"product_id": "P_SHOE_3", "similarity": 0.60},
        ]
    )

    req = RetrievalRequest(
        request_id="test_hybrid_req",
        required_category=ProductCategory.SHOES,
        max_price=10000.0,
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=10000.0)
    returned_ids = {r.product_id for r in results}

    # Verify both BM25 and Chroma candidates are in candidate union and returned
    assert "P_SHOE_1" in returned_ids
    assert "P_SHOE_2" in returned_ids
    assert "P_SHOE_3" in returned_ids

    # Verify results are sorted by relevance_score descending
    scores = [r.relevance_score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert len(results) == 3


def test_hard_category_filtering(monkeypatch):
    """Verify products from wrong category are strictly excluded despite high scores."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    # P_TOP_1 has top BM25 and Chroma scores, but wrong category ("top" != "footwear")
    monkeypatch.setattr(
        service.bm25_service,
        "search",
        lambda **kwargs: [
            {"product_id": "P_TOP_1", "bm25_score": 0.99},
            {"product_id": "P_SHOE_1", "bm25_score": 0.70},
        ]
    )
    monkeypatch.setattr(
        service.embedding_service,
        "generate_embedding",
        lambda query: [0.1] * 384
    )
    monkeypatch.setattr(
        service.chroma_service,
        "search_similar",
        lambda **kwargs: [
            {"product_id": "P_TOP_1", "similarity": 0.99},
            {"product_id": "P_SHOE_2", "similarity": 0.65},
        ]
    )

    # Ask for shoes - must NEVER return tops
    req = RetrievalRequest(
        request_id="test_req_cat",
        required_category=ProductCategory.SHOES,
        max_price=10000.0,
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=10000.0)
    assert len(results) > 0
    returned_ids = [r.product_id for r in results]
    assert "P_TOP_1" not in returned_ids
    for r in results:
        assert r.category == ProductCategory.SHOES


def test_price_filtering(monkeypatch):
    """Verify price filtering excludes products above max_price and does not treat None as 0."""
    service = get_retrieval_service()

    products = {
        "P_SHOE_IN_BUDGET": {
            "product_id": "P_SHOE_IN_BUDGET",
            "product_name": "In Budget Shoe",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "casual",
            "price": 4000.0,
            "availability": True,
        },
        "P_SHOE_OVER_BUDGET": {
            "product_id": "P_SHOE_OVER_BUDGET",
            "product_name": "Over Budget Shoe",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "casual",
            "price": 6000.0,
            "availability": True,
        },
        "P_SHOE_NO_PRICE": {
            "product_id": "P_SHOE_NO_PRICE",
            "product_name": "Missing Price Shoe",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "casual",
            "price": None,
            "availability": True,
        },
    }
    service.products = products

    monkeypatch.setattr(
        service.bm25_service,
        "search",
        lambda **kwargs: [
            {"product_id": "P_SHOE_IN_BUDGET", "bm25_score": 0.8},
            {"product_id": "P_SHOE_OVER_BUDGET", "bm25_score": 0.9},
            {"product_id": "P_SHOE_NO_PRICE", "bm25_score": 0.8},
        ]
    )
    monkeypatch.setattr(
        service.embedding_service,
        "generate_embedding",
        lambda query: [0.1] * 384
    )
    monkeypatch.setattr(
        service.chroma_service,
        "search_similar",
        lambda **kwargs: []
    )

    req = RetrievalRequest(
        request_id="test_price_req",
        required_category=ProductCategory.SHOES,
        max_price=5000.0,
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=5000.0)
    returned_ids = [r.product_id for r in results]

    # Products above price ceiling must be excluded
    assert "P_SHOE_OVER_BUDGET" not in returned_ids
    assert "P_SHOE_IN_BUDGET" in returned_ids
    assert "P_SHOE_NO_PRICE" in returned_ids

    # For P_SHOE_NO_PRICE, budget suitability must NOT be 1.0 (which would occur if treated as 0)
    no_price_result = next(r for r in results if r.product_id == "P_SHOE_NO_PRICE")
    assert no_price_result.score_breakdown.budget_suitability < 1.0
    assert no_price_result.score_breakdown.budget_suitability == 0.8


def test_excluded_product_ids(monkeypatch):
    """Verify products listed in excluded_product_ids are not returned."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    monkeypatch.setattr(
        service.bm25_service,
        "search",
        lambda **kwargs: [
            {"product_id": "P_SHOE_1", "bm25_score": 0.95},
            {"product_id": "P_SHOE_2", "bm25_score": 0.80},
        ]
    )
    monkeypatch.setattr(
        service.embedding_service,
        "generate_embedding",
        lambda query: [0.1] * 384
    )
    monkeypatch.setattr(
        service.chroma_service,
        "search_similar",
        lambda **kwargs: []
    )

    req = RetrievalRequest(
        request_id="test_excluded_req",
        required_category=ProductCategory.SHOES,
        max_price=10000.0,
        excluded_product_ids=["P_SHOE_1"],
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=10000.0)
    returned_ids = [r.product_id for r in results]
    assert "P_SHOE_1" not in returned_ids
    assert "P_SHOE_2" in returned_ids


def test_ranking_computation_and_sort_order(monkeypatch):
    """Verify RankingService.compute_score() is used and results sorted by relevance."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    monkeypatch.setattr(
        service.bm25_service,
        "search",
        lambda **kwargs: [
            {"product_id": "P_SHOE_1", "bm25_score": 0.90},
            {"product_id": "P_SHOE_2", "bm25_score": 0.30},
        ]
    )
    monkeypatch.setattr(
        service.embedding_service,
        "generate_embedding",
        lambda query: [0.1] * 384
    )
    monkeypatch.setattr(
        service.chroma_service,
        "search_similar",
        lambda **kwargs: [
            {"product_id": "P_SHOE_1", "similarity": 0.85},
            {"product_id": "P_SHOE_2", "similarity": 0.35},
        ]
    )

    req = RetrievalRequest(
        request_id="test_ranking_req",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=10000.0,
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=10000.0)
    assert len(results) >= 2

    # Scores must be sorted descending
    scores = [r.relevance_score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].product_id == "P_SHOE_1"

    # Verify score breakdown
    breakdown = results[0].score_breakdown
    assert breakdown.colour_match == 1.0
    assert breakdown.style_match == 1.0
    assert breakdown.availability == 1.0


def test_decision_logic_relaxation_ladder(monkeypatch):
    """Verify relaxation ladder behavior with sample products."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    monkeypatch.setattr(service.bm25_service, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.embedding_service, "generate_embedding", lambda q: [0.0] * 384)
    monkeypatch.setattr(service.chroma_service, "search_similar", lambda **kwargs: [])

    # Beige smart casual shoes under 5000:
    # In SAMPLE_PRODUCTS:
    # - P_SHOE_1 matches full constraints (1 match < MIN_ACCEPTABLE_RESULTS 3)
    # - Step 2 (relax colour): still 1
    # - Step 3 (relax style): still 1
    # - Step 4 (widen price +15% to 5750): P_SHOE_3 (5400) matches -> 2 matches
    # - Step 5 (best effort): returns LOW_CONFIDENCE with 2 results
    req_ok = RetrievalRequest(
        request_id="req_ok",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=5000.0,
        top_k=5
    )
    resp = resolve_retrieval(req_ok)
    assert resp.status in [RetrievalStatus.OK, RetrievalStatus.RELAXED, RetrievalStatus.LOW_CONFIDENCE]
    assert len(resp.results) > 0
    # Every returned product must strictly be SHOES
    for prod in resp.results:
        assert prod.category == ProductCategory.SHOES


def test_decision_logic_strict_ok(monkeypatch):
    """Verify relaxation ladder returns OK when sufficient results match full constraints."""
    service = get_retrieval_service()
    three_matching_shoes = {
        f"P_S_{i}": {
            "product_id": f"P_S_{i}",
            "product_name": f"Beige Loafer {i}",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "availability": True,
        }
        for i in range(1, 4)
    }
    service.products = three_matching_shoes

    monkeypatch.setattr(service.bm25_service, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.embedding_service, "generate_embedding", lambda q: [0.0] * 384)
    monkeypatch.setattr(service.chroma_service, "search_similar", lambda **kwargs: [])

    req = RetrievalRequest(
        request_id="req_strict",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=5000.0,
        top_k=5
    )
    resp = resolve_retrieval(req)
    assert resp.status == RetrievalStatus.OK
    assert len(resp.results) == 3
    assert resp.relaxed_constraints == []


def test_decision_logic_relax_colour_step(monkeypatch):
    """Verify relaxation ladder relaxes colour when colour matches are insufficient."""
    service = get_retrieval_service()
    shoes = {
        "P_S_1": {
            "product_id": "P_S_1",
            "product_name": "Beige Loafer",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "availability": True,
        },
        "P_S_2": {
            "product_id": "P_S_2",
            "product_name": "Black Loafer",
            "category": ProductCategory.SHOES.value,
            "colour": "Black",
            "style": "smart casual",
            "price": 4200.0,
            "availability": True,
        },
        "P_S_3": {
            "product_id": "P_S_3",
            "product_name": "Brown Loafer",
            "category": ProductCategory.SHOES.value,
            "colour": "Brown",
            "style": "smart casual",
            "price": 4100.0,
            "availability": True,
        },
    }
    service.products = shoes

    monkeypatch.setattr(service.bm25_service, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.embedding_service, "generate_embedding", lambda q: [0.0] * 384)
    monkeypatch.setattr(service.chroma_service, "search_similar", lambda **kwargs: [])

    req = RetrievalRequest(
        request_id="req_relax_colour",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=5000.0,
        top_k=5
    )
    resp = resolve_retrieval(req)
    assert resp.status == RetrievalStatus.RELAXED
    assert resp.relaxed_constraints == ["colour"]
    assert len(resp.results) == 3


def test_decision_logic_relax_style_step(monkeypatch):
    """Verify relaxation ladder relaxes style when colour and style matches are insufficient."""
    service = get_retrieval_service()
    shoes = {
        "P_S_1": {
            "product_id": "P_S_1",
            "product_name": "Beige Loafer",
            "category": ProductCategory.SHOES.value,
            "colour": "Beige",
            "style": "smart casual",
            "price": 4000.0,
            "availability": True,
        },
        "P_S_2": {
            "product_id": "P_S_2",
            "product_name": "Black Formal Shoe",
            "category": ProductCategory.SHOES.value,
            "colour": "Black",
            "style": "formal",
            "price": 4200.0,
            "availability": True,
        },
        "P_S_3": {
            "product_id": "P_S_3",
            "product_name": "Brown Vintage Boot",
            "category": ProductCategory.SHOES.value,
            "colour": "Brown",
            "style": "vintage",
            "price": 4100.0,
            "availability": True,
        },
    }
    service.products = shoes

    monkeypatch.setattr(service.bm25_service, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.embedding_service, "generate_embedding", lambda q: [0.0] * 384)
    monkeypatch.setattr(service.chroma_service, "search_similar", lambda **kwargs: [])

    req = RetrievalRequest(
        request_id="req_relax_style",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=5000.0,
        top_k=5
    )
    resp = resolve_retrieval(req)
    assert resp.status == RetrievalStatus.RELAXED
    assert resp.relaxed_constraints == ["colour", "style"]
    assert len(resp.results) == 3


def test_decision_logic_no_results_wrong_category():
    """Verify NO_RESULTS status when no items match category."""
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}

    # Ask for DRESS (none in SAMPLE_PRODUCTS)
    req_dress = RetrievalRequest(
        request_id="req_dress",
        required_category=ProductCategory.DRESS,
        max_price=10000.0,
        top_k=5
    )
    resp = resolve_retrieval(req_dress)
    assert resp.status == RetrievalStatus.NO_RESULTS
    assert len(resp.results) == 0
