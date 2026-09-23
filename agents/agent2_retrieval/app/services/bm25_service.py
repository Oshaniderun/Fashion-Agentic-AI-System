"""
Lexical search service using BM25 for keyword ranking over product catalog.
"""

import pickle
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

class BM25Service:
    def __init__(self, index_path: Optional[str] = None):
        self.index_path = Path(index_path) if index_path else None
        self.bm25: Optional[BM25Okapi] = None
        self.product_ids: List[str] = []
        self.product_metadata: Dict[str, Dict[str, Any]] = {}
        if self.index_path and self.index_path.exists():
            self.load_index(self.index_path)

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())

    def load_index(self, path: Path):
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.product_ids = data["product_ids"]
            self.product_metadata = data["product_metadata"]

    def build_from_products(self, products: List[Dict[str, Any]]):
        corpus = []
        self.product_ids = []
        self.product_metadata = {}

        for p in products:
            pid = p["product_id"]
            text_corpus = (
                f"{p.get('product_name', '')} {p.get('category', '')} "
                f"{p.get('subcategory', '')} {p.get('brand', '')} "
                f"{p.get('colour', '')} {p.get('material', '')} "
                f"{p.get('style', '')} {p.get('description', '')}"
            )
            tokens = self.tokenize(text_corpus)
            corpus.append(tokens)
            self.product_ids.append(pid)
            self.product_metadata[pid] = {
                "category": p.get("category"),
                "colour": p.get("colour"),
                "style": p.get("style"),
                "price": p.get("price", 0.0),
                "availability": p.get("availability", True),
                "product_name": p.get("product_name"),
                "store": p.get("store"),
                "product_url": p.get("product_url"),
            }

        self.bm25 = BM25Okapi(corpus)

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        excluded_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.product_ids:
            return []

        tokens = self.tokenize(query)
        if not tokens:
            # If no tokens in query, return neutral score for filtered items
            scores = [0.0] * len(self.product_ids)
        else:
            scores = self.bm25.get_scores(tokens)

        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        excluded_set = set(excluded_ids or [])
        matched = []

        for idx, pid in enumerate(self.product_ids):
            if pid in excluded_set:
                continue

            meta = self.product_metadata.get(pid, {})

            if category and meta.get("category") != category:
                continue

            if max_price is not None and meta.get("price", 0.0) > max_price:
                continue

            raw_score = float(scores[idx])
            # Normalize BM25 to [0, 1]
            norm_score = max(0.0, min(1.0, raw_score / max_score)) if max_score > 0 else 0.0

            matched.append({
                "product_id": pid,
                "bm25_score": norm_score,
                "metadata": meta
            })

        matched.sort(key=lambda x: x["bm25_score"], reverse=True)
        return matched[:top_k]
