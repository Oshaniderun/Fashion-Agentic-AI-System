"""
Vector database service wrapping ChromaDB with in-memory fallback.
"""

from typing import List, Dict, Any, Optional
import os
import numpy as np

class InMemoryVectorStore:
    def __init__(self):
        self.ids = []
        self.embeddings = []
        self.metadatas = []
        self.documents = []

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None, documents: Optional[List[str]] = None):
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

    def query(self, query_embeddings: List[List[float]], n_results: int = 10, where: Optional[Dict[str, Any]] = None):
        if not self.embeddings:
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
        top_matches = scores[:n_results]

        res_ids = [[x[1] for x in top_matches]]
        res_dists = [[x[0] for x in top_matches]]
        res_metas = [[x[2] for x in top_matches]]
        return {"ids": res_ids, "distances": res_dists, "metadatas": res_metas}


class ChromaService:
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "fashion_products"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._init_db()

    def _init_db(self):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            # Fallback to in-memory vector store
            self.collection = InMemoryVectorStore()

    def upsert_products(
        self,
        product_ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: Optional[List[str]] = None
    ):
        if not product_ids:
            return

        if hasattr(self.collection, "upsert"):
            self.collection.upsert(
                ids=product_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
        else:
            self.collection.add(
                ids=product_ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter
        )

        formatted_results = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i, pid in enumerate(ids):
                dist = distances[i] if i < len(distances) else 1.0
                # Cosine distance to similarity: similarity = 1 - distance
                similarity = max(0.0, min(1.0, 1.0 - dist))
                meta = metadatas[i] if i < len(metadatas) else {}
                formatted_results.append({
                    "product_id": pid,
                    "similarity": similarity,
                    "metadata": meta
                })

        return formatted_results
