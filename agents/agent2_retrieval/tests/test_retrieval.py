"""
Functional tests for Agent 2 Information Retrieval components:
BM25, Semantic search, Ranking service, and Decision logic relaxation ladder.
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
    bm25 = BM25Service()
    bm25.build_from_products(SAMPLE_PRODUCTS)

    results = bm25.search(query="beige suede loafers", top_k=5)
    assert len(results) > 0
    # P_SHOE_1 should rank #1 for "beige suede loafers"
    assert results[0]["product_id"] == "P_SHOE_1"
    assert results[0]["bm25_score"] > 0

def test_ranking_formula():
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
    # Check bounds
    assert 0.0 <= score <= 1.0
    assert breakdown.colour_match == 1.0
    assert breakdown.style_match == 1.0
    assert breakdown.availability == 1.0
    assert breakdown.semantic_similarity == round(0.5 * 0.9 + 0.5 * 0.8, 4)

def test_hard_category_filtering():
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}
    service.bm25_service.build_from_products(SAMPLE_PRODUCTS)

    # Ask for shoes - must NEVER return tops
    req = RetrievalRequest(
        request_id="test_req_cat",
        required_category=ProductCategory.SHOES,
        max_price=10000.0,
        top_k=5
    )
    results = service.search(req, relax_colour=True, relax_style=True, price_ceiling=10000.0)
    assert len(results) > 0
    for r in results:
        assert r.category == ProductCategory.SHOES

def test_decision_logic_relaxation_ladder():
    service = get_retrieval_service()
    service.products = {p["product_id"]: p for p in SAMPLE_PRODUCTS}
    service.bm25_service.build_from_products(SAMPLE_PRODUCTS)

    # 1. Full constraints match (Beige smart casual shoes under 5000) -> OK
    req_ok = RetrievalRequest(
        request_id="req_ok",
        required_category=ProductCategory.SHOES,
        preferred_colour="Beige",
        style="smart casual",
        max_price=5000.0,
        top_k=5
    )
    # Notice: we have 1 beige shoe, but MIN_ACCEPTABLE_RESULTS is 3!
    # So it should relax colour, then style, to reach >= 3 results!
    resp = resolve_retrieval(req_ok)
    assert resp.status in [RetrievalStatus.OK, RetrievalStatus.RELAXED, RetrievalStatus.LOW_CONFIDENCE]
    assert len(resp.results) > 0
    # Every returned product must strictly be SHOES
    for prod in resp.results:
        assert prod.category == ProductCategory.SHOES

def test_decision_logic_no_results_wrong_category():
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
