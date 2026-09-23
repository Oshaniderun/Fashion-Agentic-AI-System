"""
Embedding service for generating dense vector representations of fashion items and queries.
Supports SentenceTransformers with graceful fallback for offline/testing environments.
"""

from typing import List, Union
import numpy as np

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        except Exception as e:
            # Fallback for environments where sentence-transformers or torch is unavailable
            self.model = None

    def get_embedding_dimension(self) -> int:
        if self.model is not None:
            return self.model.get_sentence_embedding_dimension()
        return 384

    def generate_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings([text])[0]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self.model is not None:
            embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.tolist()

        # Deterministic hashing vector fallback if sentence-transformers is not available
        embeddings = []
        dim = self.get_embedding_dimension()
        for text in texts:
            vec = np.zeros(dim, dtype=np.float32)
            words = text.lower().split()
            if not words:
                embeddings.append(vec.tolist())
                continue
            for word in words:
                h = hash(word) % dim
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist())
        return embeddings
