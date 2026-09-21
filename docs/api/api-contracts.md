# API Contracts

Single source of truth for the JSON shape every agent sends and receives.
Update this whenever a schema changes — other members build against this,
not against your code.

## Status

| Agent | Endpoint | Request schema defined? | Response schema defined? |
|---|---|---|---|
| 1 — Wardrobe | `POST /api/agent/analyze` | ☑ | ☑ |
| 2 — Retrieval | `POST /retrieve-products` | ☑ | ☑ |
| 3 — Budget | `POST /optimize-budget` | ☐ | ☐ |
| 4 — Decision | `POST /decide-outfit` | ☐ | ☐ |

Keep the actual Pydantic models in `shared/schemas/` — this file documents them in
plain language for people who haven't read the code.

---

## Agent 1 — `POST /api/agent/analyze`

**Schema source:** `shared/schemas/agent1_schemas.py`
**Service port:** `8001`
**Owner:** Member 1 (Style & Wardrobe Intelligence Agent)

### Request (`Agent1AnalysisRequest`) — sent by: Orchestrator / Web Interface

| Field | Type | Required? | Notes |
|---|---|---|---|
| `request_id` | string | no | Correlation ID. Generated as `REQ-YYYY-XXXXXX` if not provided |
| `user_id` | integer | no | User whose wardrobe to analyze. Defaults to active user / demo |
| `query_text` | string | yes | User's natural language request (e.g. "I need something elegant but not too formal...") |
| `occasion` | string | no | Optional user explicit override |
| `style` | string | no | Optional user explicit style override |
| `colour_preference` | string | no | Optional user explicit color override |
| `budget` | float | no | Optional explicit budget ceiling in LKR |

### Response (`Agent1OutputContract`) — received by: Orchestrator / Agent 2

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | Echoes or generated correlation ID |
| `user_requirements` | object (`UserRequirements`) | Extracted `occasion`, `style` list, `colour_preferences`, `excluded_colours`, `budget` (null if not mentioned) |
| `wardrobe` | list[`WardrobeSummaryItem`] | User's owned items with detected/confirmed attributes, formality score, confidence |
| `outfit_requirements` | object (`OutfitRequirements`) | `required_categories`, `available_categories`, `missing_categories`, `optional_categories` |
| `compatible_items` | list[string] | List of wardrobe item IDs (e.g. `["W001", "W002"]`) compatible with the request |
| `compatibility` | object (`CompatibilityDetails`) | Evaluated `style`, `occasion_suitability`, `colour_compatibility`, `score` (0-1), and `explanation` |
| `confidence` | object (`ConfidenceMetrics`) | `overall`, `vision`, `nlp` |
| `search_requirements` | object (`Agent2SearchRequirement`) | Clean handoff for Agent 2: `missing_categories`, `style`, `colour`, `occasion`, `budget_remaining`, `query_text` |

### Key Invariant
- Agent 1 **never** outputs specific product recommendations or final shopping decisions.
- If no budget is specified, `budget = null`. No values are hallucinated.
- `search_requirements` formats the precise input Agent 2 needs for product retrieval.

---

## Agent 2 — `POST /retrieve-products`

**Schema source:** `shared/schemas/agent2_schemas.py` (frozen 2026-09, Stage 1)
**Decision logic:** `agents/agent2_retrieval/app/decision_logic.py`

### Request (`RetrievalRequest`) — sent by: Orchestrator / Agent 3

| Field | Type | Required? | Notes |
|---|---|---|---|
| `request_id` | string | yes | Correlation ID, carried through the whole pipeline |
| `required_category` | enum (`ProductCategory`) | yes | top / bottom / dress / outerwear / shoes / bag / jewelry / accessory |
| `preferred_colour` | string | no | e.g. `"beige"` |
| `style` | string | no | e.g. `"smart casual"` |
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
| `status` | enum (`RetrievalStatus`) | `ok` / `relaxed` / `low_confidence` / `no_results` |
| `results` | list[`ProductResult`] | ranked candidates |
| `relaxed_constraints` | list[string] | which constraints were loosened |
| `notes` | string or null | human-readable note for Agent 4's explanation step |

---

## Agent 3 — `POST /optimize-budget`
_Request / Response schema: TBD_

## Agent 4 — `POST /decide-outfit`
_Request / Response schema: TBD_
