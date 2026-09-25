"""Build Agent 2 retrieval indexes from data/processed/products_cleaned.json.

Produces (both gitignored, regenerable):
  data/processed/bm25_index.pkl   -> {"bm25": BM25Okapi, "product_ids": [...], "product_metadata": {...}}
  chroma_db/ collection "fashion_products" with all-MiniLM-L6-v2 normalized embeddings

Run inside the Agent 2 venv:
  .venv/Scripts/python scripts/build_indexes.py
"""

import json
import pickle
import sys
import time
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from app.services.bm25_service import tokenize  # noqa: E402

PRODUCTS_JSON = AGENT_DIR / "data" / "processed" / "products_cleaned.json"
BM25_OUT = AGENT_DIR / "data" / "processed" / "bm25_index.pkl"
CHROMA_DIR = AGENT_DIR / "chroma_db"
COLLECTION = "fashion_products"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH = 256
CHUNK = 1000


def doc_text(p):
    parts = [p.get("product_name") or ""]
    for key in ("description", "colour", "style", "store", "brand", "material", "category"):
        v = p.get(key)
        if v:
            parts.append(str(v))
    return " ".join(parts)


def build_bm25(products):
    corpus = [tokenize(doc_text(p)) for p in products]
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi(corpus)
    metadata = {
        p["product_id"]: {
            "category": p.get("category") or "",
            "price": p.get("price"),
            "colour": p.get("colour"),
            "style": p.get("style"),
        }
        for p in products
    }
    BM25_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_OUT, "wb") as f:
        pickle.dump({"bm25": bm25, "product_ids": [p["product_id"] for p in products],
                     "product_metadata": metadata}, f)
    print(f"BM25 index: {len(products)} docs -> {BM25_OUT}")


def chroma_metadata(p):
    meta = {"product_name": p.get("product_name") or "Unknown Product"}
    for key in ("category", "colour", "style", "store"):
        v = p.get(key)
        if v:
            meta[key] = str(v)
    if p.get("price") is not None:
        meta["price"] = float(p["price"])
    return meta


def build_chroma(products):
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR),
                                       settings=ChromaSettings(anonymized_telemetry=False))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    texts = [doc_text(p) for p in products]
    t0 = time.time()
    for start in range(0, len(products), CHUNK):
        end = min(start + CHUNK, len(products))
        vecs = model.encode(texts[start:end], batch_size=BATCH,
                            convert_to_numpy=True, normalize_embeddings=True,
                            show_progress_bar=False)
        collection.upsert(
            ids=[p["product_id"] for p in products[start:end]],
            embeddings=vecs.tolist(),
            metadatas=[chroma_metadata(p) for p in products[start:end]],
            documents=texts[start:end],
        )
        done = end
        rate = done / (time.time() - t0)
        print(f"  embedded {done}/{len(products)}  ({rate:.1f} docs/s, "
              f"ETA {(len(products) - done) / max(rate, 0.1) / 60:.1f} min)")
    print(f"Chroma collection '{COLLECTION}': {collection.count()} documents -> {CHROMA_DIR}")


def main():
    with open(PRODUCTS_JSON, "r", encoding="utf-8") as f:
        products = json.load(f)
    print(f"Loaded {len(products)} products from {PRODUCTS_JSON}")
    build_bm25(products)
    build_chroma(products)
    print("Index build complete.")


if __name__ == "__main__":
    main()
