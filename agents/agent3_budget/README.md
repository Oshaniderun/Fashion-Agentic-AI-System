# Agent 3 — Budget & Purchase Planning

**Port:** `http://127.0.0.1:8003` · prefix `/budget`

## Purpose
Turns an Agent 1 analysis + Agent 2 retrievals into concrete purchase plans under a
USD budget ceiling: deterministic cost/relevance optimization, "buy nothing" wardrobe
options, minimal-purchase alternatives, option comparison, per-user monthly quota
(free tier vs premium), and affiliate click tracking. Gemini is optional polish on
explanations only — all money math is deterministic.

## Input
`POST /budget/plan-purchases` — `Agent1OutputContract` + `retrieval_by_category` /
`retrieval_requests_by_category` (Agent 2 results), optional `user_id`, optional
`llm_polish` flag. Called by the frontend directly and by the Agent 1 pipeline handoff.

## Output
`BudgetOptimizationResponse`: budget status (feasible / partially_feasible / infeasible /
no_purchase_needed), budget source, up to N ranked options (items, totals, savings,
explanations), retrieval retry/feedback log, notes. See `app/schemas/`.

## Key endpoints
- `POST /budget/plan-purchases` — frontend-facing planner (Agent 1 contract + Agent 2 results); counts against monthly quota when `user_id` given
- `POST /budget/optimize` · `POST /budget/reoptimize` · `POST /budget/evaluate-cost`
- `POST /budget/compare-options` — side-by-side option comparison
- `GET /budget/usage/{user_id}` · `POST /budget/subscription/upgrade|downgrade`
- `POST /budget/affiliate/track-click` · `GET /budget/affiliate/history/{user_id}` · `GET /budget/affiliate/redirect/{product_id}` · `GET /budget/affiliate/stats`
- `GET /budget/health`

## Auth
Same scheme as Agents 1/2: JWT (shared `JWT_SECRET`) or `X-Service-Token`
(`AGENT_SERVICE_TOKEN`) for inter-agent calls. Config is read from the repo-root
`.env` via pydantic-settings — no separate env file.

## Database
Shares the project Postgres (`DATABASE_URL` in root `.env`). Adds two tables only:
`budget_usage_records`, `budget_affiliate_clicks` (created via SQLAlchemy metadata).

## Run
```bash
# from repo root, Windows
python -m venv agents/agent3_budget/.venv
agents/agent3_budget/.venv/Scripts/python.exe -m pip install -r agents/agent3_budget/requirements.txt
export PYTHONPATH=/d/IRWA OMP_NUM_THREADS=1
agents/agent3_budget/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003
# run from inside agents/agent3_budget so `app.main` resolves
```

## Test
```bash
cd agents/agent3_budget
PYTHONPATH=/d/IRWA OMP_NUM_THREADS=1 .venv/Scripts/python.exe -m pytest tests -q
```
LLM is mocked in tests; quota, optimizer determinism, feedback loop, and affiliate
tracking are covered there.
