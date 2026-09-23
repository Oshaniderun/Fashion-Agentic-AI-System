"""
Retrieval service orchestrating hybrid BM25 lexical search, semantic vector retrieval,
hard constraint filtering, and multi-factor ranking.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from shared.constants import ProductCategory
from shared.schemas.agent2_schemas import RetrievalRequest, ProductResult, ScoreBreakdown
from app.core.config import get_settings
from app.services.bm25_service import BM25Service
from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService
from app.services.ranking_service import RankingService
from app.models.product import Product
from app.api.dependencies import SessionLocal

_retrieval_service_instance: Optional["RetrievalService"] = None

class RetrievalService:
    def __init__(self):
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.chroma_service = ChromaService(persist_directory=self.settings.CHROMA_PERSIST_DIRECTORY)
        self.bm25_service = BM25Service(index_path=self.settings.BM25_INDEX_PATH)
        self.products: Dict[str, Dict[str, Any]] = {}
        self.reload_catalog()

    def reload_catalog(self):
        """Loads product catalog from DB or cleaned JSON file."""
        self.products.clear()
        
        # Try loading from database first
        try:
            db = SessionLocal()
            db_products = db.query(Product).all()
            if db_products:
                for p in db_products:
                    self.products[p.product_id] = {
                        "product_id": p.product_id,
                        "product_name": p.product_name,
                        "category": p.category,
                        "colour": p.colour,
                        "price": p.price,
                        "style": p.style,
                        "store": p.store or "Amazon Fashion",
                        "product_url": p.product_url,
                        "availability": bool(p.availability if p.availability is not None else True),
                        "description": p.description or ""
                    }
            db.close()
        except Exception:
            pass

        # If DB is empty, fall back to cleaned JSON
        if not self.products:
            json_path = Path(self.settings.DATASET_PATH)
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        self.products[item["product_id"]] = item

        # Build in-memory BM25 and Chroma if needed
        if self.products:
            prod_list = list(self.products.values())
            self.bm25_service.build_from_products(prod_list)

            # Chroma indexing
            chroma_count = 0
            if hasattr(self.chroma_service.collection, "count"):
                chroma_count = self.chroma_service.collection.count()
            elif hasattr(self.chroma_service.collection, "ids"):
                chroma_count = len(self.chroma_service.collection.ids)
                
            if chroma_count == 0:
                docs = [f"{p['product_name']} {p.get('description', '')}" for p in prod_list]
                pids = [p["product_id"] for p in prod_list]
                metas = [{"category": p["category"], "price": float(p.get("price")) if p.get("price") is not None else None} for p in prod_list]
                embeddings = self.embedding_service.generate_embeddings(docs)
                self.chroma_service.upsert_products(pids, embeddings, metas, docs)

    def search(
        self,
        request: RetrievalRequest,
        *,
        relax_colour: bool = False,
        relax_style: bool = False,
        price_ceiling: float
    ) -> List[ProductResult]:
        if not self.products:
            self.reload_catalog()

        req_cat_value = request.required_category.value if hasattr(request.required_category, "value") else str(request.required_category)
        excluded_ids = set(request.excluded_product_ids or [])

        # Construct search query string
        query_parts = []
        if request.query_text:
            query_parts.append(request.query_text)
        if request.preferred_colour:
            query_parts.append(request.preferred_colour)
        if request.style:
            query_parts.append(request.style)
        if request.occasion:
            query_parts.append(request.occasion)
        query_str = " ".join(query_parts) if query_parts else req_cat_value

        # Step 1: Lexical BM25 search
        bm25_results = self.bm25_service.search(
            query=query_str,
            top_k=len(self.products),
            category=req_cat_value,
            max_price=price_ceiling,
            excluded_ids=list(excluded_ids)
        )
        bm25_map = {r["product_id"]: r["bm25_score"] for r in bm25_results}

        # Step 2: Dense Vector search
        q_emb = self.embedding_service.generate_embedding(query_str)
        chroma_results = self.chroma_service.search_similar(
            query_embedding=q_emb,
            top_k=len(self.products),
            where_filter={"category": req_cat_value}
        )
        dense_map = {r["product_id"]: r["similarity"] for r in chroma_results}

        # Candidate pool: all products in required category within price ceiling
        candidates: List[ProductResult] = []

        for pid, prod in self.products.items():
            if pid in excluded_ids:
                continue

            # Category is strictly enforced (never relaxed)
            if prod.get("category") != req_cat_value:
                continue

            # Price ceiling enforced
            price = float(prod.get("price")) if prod.get("price") is not None else None
            if price is not None and price > price_ceiling:
                continue

            # Hard colour constraint (unless relaxed)
            prod_colour = prod.get("colour", "")
            if not relax_colour and request.preferred_colour:
                req_col = request.preferred_colour.strip().lower()
                p_col = prod_colour.strip().lower()
                if req_col not in p_col and p_col not in req_col:
                    continue

            # Hard style constraint (unless relaxed)
            prod_style = prod.get("style", "")
            if not relax_style and request.style:
                req_sty = request.style.strip().lower()
                p_sty = prod_style.strip().lower()
                if req_sty not in p_sty and p_sty not in req_sty:
                    continue

            bm25_score = bm25_map.get(pid, 0.0)
            dense_score = dense_map.get(pid, 0.5)

            weighted_relevance, breakdown = RankingService.compute_score(
                bm25_score=bm25_score,
                dense_similarity=dense_score,
                product_price=price,
                max_price=request.max_price,
                product_colour=prod_colour,
                requested_colour=request.preferred_colour,
                product_style=prod_style,
                requested_style=request.style,
                is_available=bool(prod.get("availability", True)),
            )

            # Ensure valid URL
            raw_url = prod.get("product_url") or f"https://www.amazon.com/dp/{pid}"
            if not raw_url.startswith("http"):
                raw_url = f"https://www.amazon.com/dp/{pid}"

            product_result = ProductResult(
                product_id=pid,
                name=prod.get("product_name", "Unknown Product"),
                category=ProductCategory(prod.get("category")),
                colour=prod_colour,
                price=price,
                store=prod.get("store", "Amazon Fashion"),
                url=raw_url,
                availability=bool(prod.get("availability", True)),
                relevance_score=weighted_relevance,
                score_breakdown=breakdown
            )
            candidates.append(product_result)

        # Sort candidates by relevance_score descending
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        return candidates[:request.top_k]

def get_retrieval_service() -> RetrievalService:
    global _retrieval_service_instance
    if _retrieval_service_instance is None:
        _retrieval_service_instance = RetrievalService()
    return _retrieval_service_instance
