# Agent 2 — Fashion Information Retrieval

**Status:** Stage 3 Implemented & Verified.

## Purpose
Agent 2 is a standalone FastAPI service responsible for retrieving fashion products from a historical catalogue (Amazon Fashion 2023) using hybrid search techniques (BM25 lexical search + Sentence Transformers semantic embeddings + Multi-factor ranking).

It owns one genuine decision point: the **relaxation ladder** in `app/decision_logic.py` which dynamically relaxes constraints when queries return too few usable matches, while guaranteeing that `required_category` is strictly preserved.

## Database Boundary & Isolation
- **Agent 1 / Wardrobe DB**: Stores user personal wardrobe items and preferences.
- **Agent 2 Product DB**: Strictly isolates purchasable product catalogue data. Agent 2 never stores or requests user wardrobe items, images, or personal PII.

## Architecture & Components

```text
agents/agent2_retrieval/
├── app/
│   ├── main.py                  # FastAPI application with security handlers & lifespan
│   ├── api/
│   │   ├── dependencies.py      # Resilient DB connection & Bearer JWT/Service token auth
│   │   └── routes.py            # /health, /retrieve-products, /api/v1/products/{id}
│   ├── core/
│   │   ├── config.py            # Settings & environment variables
│   │   └── security.py          # JWT validation & inter-agent token checks
│   ├── models/
│   │   └── product.py           # SQLAlchemy ORM Product model
│   ├── repositories/
│   │   └── product_repository.py# Product data access layer
│   ├── schemas/
│   │   ├── product.py           # Product Pydantic schemas
│   │   └── search.py            # Search DTOs
│   ├── services/
│   │   ├── bm25_service.py      # BM25 lexical keyword search
│   │   ├── embedding_service.py # Dense vector embedding generation
│   │   ├── chroma_service.py    # ChromaDB / in-memory vector store
│   │   ├── ranking_service.py   # Multi-factor score formula + ScoreBreakdown
│   │   └── retrieval_service.py # Hybrid search orchestrator
│   └── decision_logic.py        # Constraint relaxation ladder
├── data/
│   ├── raw/                     # Raw Amazon Fashion 2023 catalog
│   └── processed/               # Cleaned products & precomputed BM25 index
├── scripts/
│   ├── preprocess_data.py       # Validates and cleans raw dataset
│   ├── load_products.py         # Ingests products into DB
│   ├── build_bm25.py            # Builds BM25 index
│   └── build_embeddings.py      # Indexes vectors into ChromaDB
├── tests/
│   ├── test_api.py              # FastAPI endpoint tests
│   ├── test_retrieval.py        # BM25, ranking & relaxation ladder tests
│   └── test_security.py         # 15+ comprehensive security attack tests
├── Dockerfile
└── requirements.txt
```

## Relevance Scoring Formula
$$Relevance = 0.30 \cdot Semantic + 0.25 \cdot Colour + 0.20 \cdot Style + 0.15 \cdot Budget + 0.10 \cdot Availability$$

Transparently reported to upstream agents via `ScoreBreakdown`.

## Relaxation Ladder
1. Full constraints (category + colour + style + price).
2. Relax colour (drop hard filter; keep as soft semantic ranking).
3. Relax style (drop hard filter; keep as soft semantic ranking).
4. Widen max_price ceiling by +15% (single step).
5. Best-effort results flagged `low_confidence` (or `no_results` if empty).

*`required_category` is never relaxed.*

## Running Locally

```bash
# Activate virtual environment
venv\Scripts\activate

# Run service
uvicorn app.main:app --port 8002 --reload
```

## Running Tests

```bash
pytest tests/ -v
```
