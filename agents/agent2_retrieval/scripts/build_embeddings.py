"""
Generate and index embeddings for products into ChromaDB vector store.
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

from app.services.embedding_service import EmbeddingService
from app.services.chroma_service import ChromaService, InMemoryVectorStore
from app.core.config import get_settings

EMBED_BATCH_SIZE = 256
CHROMA_UPSERT_BATCH = 2000


def _text_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def chroma_metadata(product: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma rejects None; omit missing optional fields instead of inventing defaults."""
    meta: Dict[str, Any] = {"product_id": product["product_id"]}
    for key in ("product_name", "category", "colour", "style", "store"):
        value = product.get(key)
        if value is not None and value != "":
            meta[key] = str(value)
    price = product.get("price")
    if price is not None:
        meta["price"] = float(price)
    availability = product.get("availability")
    if availability is not None:
        meta["availability"] = bool(availability)
    return meta


def embedding_document(product: Dict[str, Any]) -> str:
    parts = [f"Title: {_text_or_empty(product.get('product_name'))}"]
    for label, key in (
        ("Category", "category"),
        ("Colour", "colour"),
        ("Style", "style"),
        ("Brand", "brand"),
        ("Material", "material"),
        ("Description", "description"),
    ):
        value = product.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return ". ".join(parts)


def build_product_embeddings(products_file: Path, persist_dir: str):
    if not products_file.exists():
        raise FileNotFoundError(f"Cleaned products file not found at: {products_file}")

    persist_path = Path(persist_dir)
    if not persist_path.is_absolute():
        persist_path = (agent_dir / persist_path).resolve()

    with open(products_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    embed_svc = EmbeddingService()
    if embed_svc.model is None:
        raise RuntimeError(
            "Sentence Transformer model failed to load. "
            "Install sentence-transformers (and torch) before building production embeddings."
        )

    chroma_svc = ChromaService(persist_directory=str(persist_path))
    if isinstance(chroma_svc.collection, InMemoryVectorStore):
        raise RuntimeError(
            "ChromaDB persistent client was not created. "
            "Install chromadb before building the production vector store."
        )

    print(f"Embedding model: {embed_svc.model_name}")
    print(f"Embedding dimension: {embed_svc.get_embedding_dimension()}")
    print(f"Chroma persist directory: {persist_path}")
    print(f"Chroma collection: {chroma_svc.collection_name}")
    print(f"Generating embeddings for {len(products)} products...")

    indexed = 0
    for start in range(0, len(products), EMBED_BATCH_SIZE):
        batch = products[start:start + EMBED_BATCH_SIZE]
        product_ids = [p["product_id"] for p in batch]
        documents = [embedding_document(p) for p in batch]
        metadatas = [chroma_metadata(p) for p in batch]
        embeddings = embed_svc.generate_embeddings(documents)

        for chroma_start in range(0, len(product_ids), CHROMA_UPSERT_BATCH):
            chroma_svc.upsert_products(
                product_ids=product_ids[chroma_start:chroma_start + CHROMA_UPSERT_BATCH],
                embeddings=embeddings[chroma_start:chroma_start + CHROMA_UPSERT_BATCH],
                metadatas=metadatas[chroma_start:chroma_start + CHROMA_UPSERT_BATCH],
                documents=documents[chroma_start:chroma_start + CHROMA_UPSERT_BATCH],
            )

        indexed += len(product_ids)
        if indexed % 2048 == 0 or indexed == len(products):
            print(f"  indexed {indexed}/{len(products)}", flush=True)

    print(f"Embedding indexing complete. {indexed} items indexed.")


if __name__ == "__main__":
    settings = get_settings()
    processed_path = agent_dir / "data" / "processed" / "products_cleaned.json"
    build_product_embeddings(processed_path, settings.CHROMA_PERSIST_DIRECTORY)
