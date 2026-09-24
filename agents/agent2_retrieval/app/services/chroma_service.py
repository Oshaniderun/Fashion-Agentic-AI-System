"""
Vector database service wrapping ChromaDB with persistent client management,
in-memory fallback, collection count inspection, and similarity searching.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

try:
    from app.core.config import get_settings
except ImportError:
    get_settings = None

from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

# Process-level cache for ChromaService instance / PersistentClient
_CHROMA_SERVICE_INSTANCE: Optional["ChromaService"] = None


class InMemoryVectorStore:
    """
    In-memory fallback vector store for environments where chromadb is unavailable
    or for isolated testing environments.
    """

    def __init__(self):
        self.ids: List[str] = []
        self.embeddings: List[List[float]] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.documents: List[str] = []

    def count(self) -> int:
        return len(self.ids)

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ) -> None:
        for i, doc_id in enumerate(ids):
            if doc_id in self.ids:
                idx = self.ids.index(doc_id)
                self.embeddings[idx] = embeddings[i]
                if metadatas:
                    self.metadatas[idx] = metadatas[i]
                if documents:
                    self.documents[idx] = documents[i]
            else:
                self.ids.append(doc_id)
                self.embeddings.append(embeddings[i])
                self.metadatas.append(metadatas[i] if metadatas else {})
                self.documents.append(documents[i] if documents else "")

    def upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ) -> None:
        self.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.embeddings or not query_embeddings or not query_embeddings[0]:
            return {"ids": [[]], "distances": [[]], "metadatas": [[]]}

        q_vec = np.array(query_embeddings[0], dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scores = []
        for idx, (doc_id, emb, meta) in enumerate(zip(self.ids, self.embeddings, self.metadatas)):
            # Check where filter
            if where:
                match = True
                for k, v in where.items():
                    if k == "$and":
                        for clause in v:
                            for ck, cv in clause.items():
                                if meta.get(ck) != cv:
                                    match = False
                                    break
                    elif meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            d_vec = np.array(emb, dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            if d_norm > 0:
                d_vec = d_vec / d_norm

            sim = float(np.dot(q_vec, d_vec))
            # Distance = 1 - cosine_similarity
            dist = max(0.0, 1.0 - sim)
            scores.append((dist, doc_id, meta))

        scores.sort(key=lambda x: x[0])
        n_results = max(1, min(n_results, len(scores))) if scores else n_results
        top_matches = scores[:n_results]

        res_ids = [[x[1] for x in top_matches]]
        res_dists = [[x[0] for x in top_matches]]
        res_metas = [[x[2] for x in top_matches]]
        return {"ids": res_ids, "distances": res_dists, "metadatas": res_metas}


class ChromaService:
    """
    Service wrapping ChromaDB persistent vector database.
    Provides collection management, count retrieval, similarity search,
    and safe query parameter handling.
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = "fashion_products"
    ):
        if persist_directory is None:
            if get_settings is not None:
                try:
                    settings = get_settings()
                    persist_directory = getattr(settings, "CHROMA_PERSIST_DIRECTORY", "./chroma_db")
                except Exception:
                    persist_directory = "./chroma_db"
            else:
                persist_directory = "./chroma_db"

        self.persist_directory: str = persist_directory
        self.collection_name: str = collection_name or "fashion_products"
        self.client: Any = None
        self.collection: Any = None
        self._init_db()

    def _init_db(self) -> None:
        """Initializes persistent ChromaDB client and accesses the target collection."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            target_path = Path(self.persist_directory)
            if target_path.is_absolute() and target_path.exists():
                abs_path = target_path
            else:
                agent_dir = Path(__file__).resolve().parent.parent.parent
                workspace_dir = agent_dir.parent.parent

                candidate_agent = (agent_dir / self.persist_directory).resolve()
                candidate_ws = (workspace_dir / self.persist_directory).resolve()
                candidate_direct = target_path.resolve()

                if candidate_direct.exists() and (candidate_direct / "chroma.sqlite3").exists():
                    abs_path = candidate_direct
                elif candidate_agent.exists() and (candidate_agent / "chroma.sqlite3").exists():
                    abs_path = candidate_agent
                elif candidate_ws.exists() and (candidate_ws / "chroma.sqlite3").exists():
                    abs_path = candidate_ws
                elif candidate_agent.exists():
                    abs_path = candidate_agent
                elif candidate_direct.exists():
                    abs_path = candidate_direct
                else:
                    abs_path = candidate_agent

            os.makedirs(abs_path, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(abs_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
            logger.info(
                f"Connected to ChromaDB at '{abs_path}' for collection '{self.collection_name}'."
            )
        except Exception as e:
            logger.warning(
                f"Failed to initialize persistent ChromaDB client at '{self.persist_directory}': {e}. "
                "Using in-memory fallback vector store."
            )
            self.collection = InMemoryVectorStore()

    def count(self) -> int:
        """Returns the total number of items in the vector collection."""
        return self.get_count()

    def get_count(self) -> int:
        """Returns the total number of items in the vector collection."""
        if hasattr(self.collection, "count"):
            try:
                return int(self.collection.count())
            except Exception:
                pass
        if hasattr(self.collection, "ids"):
            return len(self.collection.ids)
        return 0

    def search_similar(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        top_k: int = 10,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity search against the ChromaDB vector store.

        Args:
            query_embedding: Dense vector for query text (384 dimensions for all-MiniLM-L6-v2).
            query_text: Free-text query string (converted to embedding if query_embedding is None).
            top_k: Number of nearest items to retrieve.
            where_filter: Metadata filtering options compatible with ChromaDB schema.

        Returns:
            List of dicts containing product_id, similarity (0.0 to 1.0), distance, and metadata.
        """
        # 1. Validate / resolve embedding
        if query_embedding is None and query_text is not None and isinstance(query_text, str) and query_text.strip():
            embed_svc = get_embedding_service()
            query_embedding = embed_svc.generate_embedding(query_text)

        if not query_embedding or not isinstance(query_embedding, list):
            logger.warning("Empty or invalid query_embedding provided to ChromaService.search_similar.")
            return []

        # 2. Validate top_k
        if not isinstance(top_k, int) or top_k < 1:
            top_k = 10

        total_count = self.get_count()
        if total_count > 0:
            top_k = min(top_k, total_count)
        else:
            top_k = min(top_k, 200)

        # 3. Query collection
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter if where_filter else None
            )
        except Exception as e:
            logger.error(f"Error querying ChromaDB collection '{self.collection_name}': {e}")
            return []

        # 4. Format results
        formatted_results: List[Dict[str, Any]] = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i, pid in enumerate(ids):
                dist = float(distances[i]) if i < len(distances) and distances[i] is not None else 1.0
                similarity = max(0.0, min(1.0, 1.0 - dist))
                meta = metadatas[i] if i < len(metadatas) and metadatas[i] is not None else {}

                formatted_results.append({
                    "product_id": pid,
                    "similarity": similarity,
                    "distance": dist,
                    "metadata": meta
                })

        return formatted_results

    def upsert_products(
        self,
        product_ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: Optional[List[str]] = None
    ) -> None:
        """
        Upserts products into the collection. Used by dataset index building scripts.
        """
        if not product_ids:
            return

        if hasattr(self.collection, "upsert"):
            self.collection.upsert(
                ids=product_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
        elif hasattr(self.collection, "add"):
            self.collection.add(
                ids=product_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )


def get_chroma_service(
    persist_directory: Optional[str] = None,
    collection_name: Optional[str] = "fashion_products"
) -> ChromaService:
    """Returns a process-wide reusable instance of ChromaService."""
    global _CHROMA_SERVICE_INSTANCE
    if _CHROMA_SERVICE_INSTANCE is None:
        _CHROMA_SERVICE_INSTANCE = ChromaService(
            persist_directory=persist_directory,
            collection_name=collection_name
        )
    return _CHROMA_SERVICE_INSTANCE
