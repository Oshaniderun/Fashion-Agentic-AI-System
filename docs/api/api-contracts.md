# API Contracts

Single source of truth for the JSON shape every agent sends and receives.
Update this whenever a schema changes — other members build against this,
not against your code.

## Status

| Agent | Endpoint | Request schema defined? | Response schema defined? |
|---|---|---|---|
| 1 — Wardrobe | `POST /analyze-wardrobe` | ☐ | ☐ |
| 2 — Retrieval | `POST /retrieve-products` | ☑ | ☑ |
| 3 — Budget | `POST /optimize-budget` | ☐ | ☐ |
| 4 — Decision | `POST /decide-outfit` | ☐ | ☐ |

Keep the actual Pydantic models in `shared/schemas/` — this file documents them in
plain language for people who haven't read the code.

---

## Agent 1 — `POST /analyze-wardrobe`
_Request / Response schema: TBD_

## Agent 2 — `POST /retrieve-products`

**Schema source:** `shared/schemas/agent2_schemas.py` (frozen 2026-09, Stage 1)
**Decision logic:** `agents/agent2_retrieval/app/decision_logic.py`

### Request (`RetrievalRequest`) — sent by: Orchestrator / Agent 3

| Field | Type | Required? | Notes |
|---|---|---|---|
| `request_id` | string | yes | Correlation ID, carried through the whole pipeline |
| `required_category` | enum (`ProductCategory`) | yes | top / bottom / dress / outerwear / shoes / bag / jewelry / accessory |
| `preferred_colour` | string | no | e.g. `"beige"` |
| `style` | string | no | e.g. `"smart casual"` — free text until Agent 1 finalizes a style taxonomy |
| `occasion` | string | no | passed through from Agent 1, not validated by Agent 2 |
| `query_text` | string | no | free-text query for the BM25/semantic side of retrieval |
| `max_price` | float | yes | ceiling in LKR for this single item |
| `top_k` | int | no (default 5) | how many ranked results to return |
| `is_retry` | bool | no (default false) | true when Agent 4 rejected a previous candidate and Agent 3 is asking again |
| `retry_count` | int | no (default 0) | capped at 3 by the Orchestrator |
| `excluded_product_ids` | list[string] | no | products already rejected this session — must not be returned again |

### Response (`RetrievalResponse`) — received by: Orchestrator / Agent 3

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | echoes the request's ID |
| `status` | enum (`RetrievalStatus`) | `ok` / `relaxed` / `low_confidence` / `no_results` — see decision logic below |
| `results` | list[`ProductResult`] | ranked candidates |
| `relaxed_constraints` | list[string] | which constraints were loosened, e.g. `["colour", "price_ceiling+15%"]` |
| `notes` | string or null | human-readable note for Agent 4's explanation step |

Each `ProductResult` carries `product_id`, `name`, `category`, `colour`, `price`,
`store`, `url`, `availability`, an overall `relevance_score`, and a
`score_breakdown` (`semantic_similarity`, `colour_match`, `style_match`,
`budget_suitability`, `availability`) matching the weighted formula from the
project proposal (0.30 / 0.25 / 0.20 / 0.15 / 0.10).

### Decision logic (Agent 2's one genuine decision point)

If a query returns fewer than 3 matches, Agent 2 relaxes constraints one at a
time — colour, then style, then a single +15% widening of the price ceiling —
before returning best-effort results flagged `low_confidence`.
`required_category` is never relaxed. Full ladder is in
`agents/agent2_retrieval/app/decision_logic.py`.

### Security note

Product `name`/`description` text is external, unauthenticated data. It is
displayed, never treated as an instruction or concatenated unguarded into an
LLM prompt — this is the intended attack surface for the IR & Security
individual assessment.

## Agent 3 — `POST /optimize-budget`
_Request / Response schema: TBD_

## Agent 4 — `POST /decide-outfit`
_Request / Response schema: TBD_
