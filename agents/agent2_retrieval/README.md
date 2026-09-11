# Agent 2 — Fashion Information Retrieval

**Status:** Stage 1 defined (2026-09) — schemas and decision logic written;
the retrieval engine itself is not implemented yet (that's Stage 3).

## Purpose
Find and rank fashion products that satisfy a structured requirement produced
upstream (originally by Agent 1, sometimes re-issued by Agent 3 on a budget
retry). Owns one genuine decision point: when a query returns too few
matches, decide how to relax constraints before giving up — see
`app/decision_logic.py`.

## Input
`RetrievalRequest` — defined in `shared/schemas/agent2_schemas.py`.
Plain-language field list: `docs/api/api-contracts.md`.

## Output
`RetrievalResponse` — defined in `shared/schemas/agent2_schemas.py`.
Includes ranked `ProductResult`s with a full score breakdown, a `status`
flag (`ok` / `relaxed` / `low_confidence` / `no_results`), and which
constraints (if any) were relaxed to produce the results.

## Decision logic
See `app/decision_logic.py` for the relaxation ladder (colour → style →
+15% price ceiling → best-effort) and the rule for treating retrieved
product text as untrusted data, never as instructions.

## Not yet done (Stage 2 / Stage 3)
- Product dataset (`data/products.csv` or similar) — see `data/README.md`
- Real BM25 + Sentence-Transformers retrieval engine wired into
  `_run_retrieval()` in `decision_logic.py`
- FastAPI route (`app/main.py`) exposing `POST /retrieve-products`

## Run
```
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```
(Won't actually start yet — `app/main.py` doesn't exist until Stage 3.)
