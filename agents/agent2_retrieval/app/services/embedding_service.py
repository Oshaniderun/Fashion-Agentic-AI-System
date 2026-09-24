"""
Embedding service for generating dense vector representations of fashion items and queries.
Supports SentenceTransformers with graceful fallback for offline/testing environments.
Uses model caching to prevent repeated model loading within the same process.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import numpy as np

try:
    from app.core.config import get_settings
except ImportError:
    get_settings = None

logger = logging.getLogger(__name__)

# Process-level cache for loaded SentenceTransformer models to avoid redundant reloads
_MODEL_CACHE: Dict[str, Any] = {}


class EmbeddingService:
    """
    Service for generating vector embeddings for single queries or batches of text.
    Provides compatibility with ChromaDB and handles invalid/empty inputs safely.
    """

    def __init__(self, model_name: Optional[str] = None):
        if model_name is None:
            if get_settings is not None:
                try:
                    settings = get_settings()
                    model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
                except Exception:
                    model_name = "all-MiniLM-L6-v2"
            else:
                model_name = "all-MiniLM-L6-v2"

        self.model_name: str = model_name
        self.model: Any = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads the SentenceTransformer model into process cache or retrieves it if cached."""
        global _MODEL_CACHE
        if self.model_name in _MODEL_CACHE:
            self.model = _MODEL_CACHE[self.model_name]
            return

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            model = SentenceTransformer(self.model_name)
            _MODEL_CACHE[self.model_name] = model
            self.model = model
        except Exception as e:
            logger.warning(
                f"Failed to load SentenceTransformer model '{self.model_name}': {e}. "
                "Using fallback deterministic vector generator."
            )
            self.model = None

    def get_embedding_dimension(self) -> int:
        """Returns the output vector dimension of the current embedding model (default 384)."""
        if self.model is not None:
            try:
                if hasattr(self.model, "get_embedding_dimension"):
                    return int(self.model.get_embedding_dimension())
                return int(self.model.get_sentence_embedding_dimension())
            except Exception:
                return 384
        return 384

    def encode_query(self, text: str) -> List[float]:
        """Encodes a single text query into a dense vector embedding."""
        return self.generate_embedding(text)

    def generate_embedding(self, text: str) -> List[float]:
        """Encodes a single text query into a dense vector embedding."""
        results = self.generate_embeddings([text])
        if results:
            return results[0]
        return [0.0] * self.get_embedding_dimension()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encodes a batch of texts into dense vector embeddings."""
        return self.generate_embeddings(texts)

    def generate_embeddings(self, texts: List[Union[str, None]]) -> List[List[float]]:
        """
        Encodes multiple text items into embeddings suitable for vector store indexing.
        Safely handles empty, None, or non-string inputs by returning zero-vectors.
        """
        if not texts:
            return []

        dim = self.get_embedding_dimension()

        # Pre-process and identify valid vs invalid inputs
        cleaned_texts: List[str] = []
        valid_indices: List[int] = []

        for i, raw_text in enumerate(texts):
            if raw_text is not None and isinstance(raw_text, str) and raw_text.strip():
                cleaned_texts.append(raw_text.strip())
                valid_indices.append(i)

        output_embeddings: List[List[float]] = [[0.0] * dim for _ in range(len(texts))]

        if not valid_indices:
            return output_embeddings

        if self.model is not None:
            try:
                encoded = self.model.encode(
                    cleaned_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
                if isinstance(encoded, np.ndarray):
                    encoded_list = encoded.tolist()
                else:
                    encoded_list = [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in encoded]

                for idx_in_valid, orig_idx in enumerate(valid_indices):
                    output_embeddings[orig_idx] = [float(v) for v in encoded_list[idx_in_valid]]
                return output_embeddings
            except Exception as e:
                logger.error(f"Error during model encoding: {e}. Falling back to deterministic hashing.")

        # Deterministic hashing fallback
        for idx_in_valid, orig_idx in enumerate(valid_indices):
            text = cleaned_texts[idx_in_valid]
            vec = np.zeros(dim, dtype=np.float32)
            words = text.lower().split()
            for word in words:
                h = hash(word) % dim
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            output_embeddings[orig_idx] = vec.tolist()

        return output_embeddings


_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service(model_name: Optional[str] = None) -> EmbeddingService:
    """Returns a process-wide reusable instance of EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None or (model_name and _embedding_service_instance.model_name != model_name):
        _embedding_service_instance = EmbeddingService(model_name=model_name)
    return _embedding_service_instance
