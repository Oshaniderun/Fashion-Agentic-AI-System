"""
Lexical search service using BM25 for keyword ranking over product catalog.
Loads and caches precomputed BM25 index and supports filtering and fast keyword search.
"""

import logging
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from rank_bm25 import BM25Okapi

try:
    from app.core.config import get_settings
except ImportError:
    get_settings = None

logger = logging.getLogger(__name__)

# Process-level cache for loaded BM25 index data (path -> index_dict)
_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}
_BM25_SERVICE_INSTANCE: Optional["BM25Service"] = None


def tokenize(text: str) -> List[str]:
    """Tokenizes text consistently with the index construction."""
    if not text or not isinstance(text, str):
        return []
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())


def resolve_index_path(index_path: Optional[Union[str, Path]] = None) -> Path:
    """Robustly resolves index path across working directories."""
    if index_path is None:
        if get_settings is not None:
            try:
                settings = get_settings()
                index_path = getattr(settings, "BM25_INDEX_PATH", "./data/processed/bm25_index.pkl")
            except Exception:
                index_path = "./data/processed/bm25_index.pkl"
        else:
            index_path = "./data/processed/bm25_index.pkl"

    target_path = Path(index_path)
    if target_path.is_absolute() and target_path.exists():
        return target_path

    agent_dir = Path(__file__).resolve().parent.parent.parent
    workspace_dir = agent_dir.parent.parent

    candidate_direct = target_path.resolve()
    candidate_agent = (agent_dir / index_path).resolve()
    candidate_ws = (workspace_dir / index_path).resolve()

    if candidate_direct.exists() and candidate_direct.is_file():
        return candidate_direct
    if candidate_agent.exists() and candidate_agent.is_file():
        return candidate_agent
    if candidate_ws.exists() and candidate_ws.is_file():
        return candidate_ws

    return candidate_agent


class BM25Service:
    """
    Service wrapping BM25Okapi for keyword-based retrieval.
    Provides indexing, search with score normalization, and metadata filtering.
    """

    def __init__(self, index_path: Optional[Union[str, Path]] = None, auto_load: bool = True):
        self.index_path: Path = resolve_index_path(index_path)
        self.bm25: Optional[BM25Okapi] = None
        self.product_ids: List[str] = []
        self.product_metadata: Dict[str, Dict[str, Any]] = {}

        if auto_load and self.index_path.exists():
            self.load_index(self.index_path)

    def tokenize(self, text: str) -> List[str]:
        return tokenize(text)

    def count(self) -> int:
        """Returns the total number of indexed documents."""
        return len(self.product_ids)

    def get_count(self) -> int:
        """Returns the total number of indexed documents."""
        return len(self.product_ids)

    def load_index(self, path: Union[str, Path]) -> None:
        """Loads precomputed index using process-level cache."""
        global _INDEX_CACHE
        resolved_path = str(Path(path).resolve())

        if resolved_path in _INDEX_CACHE:
            cached = _INDEX_CACHE[resolved_path]
            self.bm25 = cached["bm25"]
            self.product_ids = cached["product_ids"]
            self.product_metadata = cached.get("product_metadata", {})
            return

        with open(resolved_path, "rb") as f:
            data = pickle.load(f)

        _INDEX_CACHE[resolved_path] = data
        self.bm25 = data["bm25"]
        self.product_ids = data["product_ids"]
        self.product_metadata = data.get("product_metadata", {})
        logger.info(f"Loaded BM25 index from '{resolved_path}' with {len(self.product_ids)} documents.")

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        excluded_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs lexical keyword search using BM25 with score normalization.

        Args:
            query: Keyword search string.
            top_k: Number of ranked results to return.
            category: Optional category constraint.
            max_price: Optional maximum price ceiling.
            excluded_ids: Optional list of product IDs to exclude.

        Returns:
            List of dicts containing product_id, bm25_score (0.0 to 1.0), and metadata.
        """
        if not self.bm25 or not self.product_ids:
            return []

        # Validate query
        if not query or not isinstance(query, str) or not query.strip():
            return []

        tokens = self.tokenize(query)
        if not tokens:
            return []

        # Validate / clamp top_k
        if not isinstance(top_k, int) or top_k <= 0:
            return []

        top_k = min(top_k, len(self.product_ids))

        # Score documents
        raw_scores = self.bm25.get_scores(tokens)
        max_score = float(np.max(raw_scores)) if len(raw_scores) > 0 and np.max(raw_scores) > 0 else 0.0

        excluded_set = set(excluded_ids or [])
        matched = []

        for idx, pid in enumerate(self.product_ids):
            if pid in excluded_set:
                continue

            meta = self.product_metadata.get(pid, {})

            if category and meta.get("category") != category:
                continue

            if max_price is not None:
                raw_price = meta.get("price")
                if raw_price is not None:
                    try:
                        if float(raw_price) > max_price:
                            continue
                    except (ValueError, TypeError):
                        pass

            score_val = float(raw_scores[idx])
            # If no filters applied and score is 0, skip document unless category was specified
            if category is None and max_price is None and score_val <= 0.0:
                continue

            norm_score = max(0.0, min(1.0, score_val / max_score)) if max_score > 0 else 0.0

            result_entry = {
                "product_id": pid,
                "bm25_score": round(norm_score, 4)
            }
            if meta:
                result_entry["metadata"] = meta

            matched.append(result_entry)

        matched.sort(key=lambda x: x["bm25_score"], reverse=True)
        return matched[:top_k]


def get_bm25_service(index_path: Optional[Union[str, Path]] = None) -> BM25Service:
    """Returns a process-wide reusable instance of BM25Service."""
    global _BM25_SERVICE_INSTANCE
    if _BM25_SERVICE_INSTANCE is None:
        _BM25_SERVICE_INSTANCE = BM25Service(index_path=index_path)
    return _BM25_SERVICE_INSTANCE
