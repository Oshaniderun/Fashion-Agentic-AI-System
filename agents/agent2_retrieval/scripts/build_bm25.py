"""
Precompute BM25 index from cleaned product catalog.
"""

import json
import pickle
import re
from pathlib import Path
import sys

current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

def tokenize(text: str):
    if not text:
        return []
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())

def build_bm25_index(products_file: Path, output_file: Path):
    from rank_bm25 import BM25Okapi

    if not products_file.exists():
        raise FileNotFoundError(f"Cleaned products file not found at: {products_file}")

    with open(products_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    corpus = []
    product_ids = []
    product_metadata = {}

    def field(p, key):
        value = p.get(key)
        return value if value is not None else ""

    for p in products:
        pid = p["product_id"]
        # Concatenate salient search fields (skip missing/NULL values)
        text_corpus = (
            f"{field(p, 'product_name')} {field(p, 'category')} "
            f"{field(p, 'subcategory')} {field(p, 'brand')} "
            f"{field(p, 'colour')} {field(p, 'material')} "
            f"{field(p, 'style')} {field(p, 'description')}"
        )
        tokens = tokenize(text_corpus)
        corpus.append(tokens)
        product_ids.append(pid)
        product_metadata[pid] = {
            "category": p.get("category"),
            "colour": p.get("colour"),
            "style": p.get("style"),
            "price": p.get("price"),
            "availability": p.get("availability"),
            "product_name": p.get("product_name"),
            "store": p.get("store"),
            "product_url": p.get("product_url"),
        }

    bm25 = BM25Okapi(corpus)

    index_data = {
        "bm25": bm25,
        "product_ids": product_ids,
        "product_metadata": product_metadata,
        "corpus_tokens": corpus
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "wb") as f:
        pickle.dump(index_data, f)

    print(f"BM25 index built successfully:")
    print(f"  - Indexed documents: {len(product_ids)}")
    print(f"  - Saved to: {output_file}")

if __name__ == "__main__":
    processed_path = agent_dir / "data" / "processed" / "products_cleaned.json"
    index_path = agent_dir / "data" / "processed" / "bm25_index.pkl"
    build_bm25_index(processed_path, index_path)
