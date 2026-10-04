# Agent 4 — Outfit Decision & Personalization

**Status:** implemented and running on port **8004**.

## Purpose

Agent 4 is the decision layer. It takes the *already validated* outputs of the
other three agents and answers one question: **which single outfit should the
user get, why, and how confident are we?**

- Input: the cached Agent 1 output, the Agent 2 retrieval responses and the
  Agent 3 budget response, supplied verbatim by the caller (orchestrator or
  frontend).
- Output: one chosen outfit, a confidence score and level, an explanation, plus
  the additive decision-transparency fields described below.
- It never re-derives another agent's work: no outbound calls, no shared
  database reads, no budget arithmetic of its own. Feasibility and prices are
  taken from Agent 3 exactly as supplied.

## Run

```bash
cd agents/agent4_decision
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8004                        # no --reload: see note below
```

Config comes from the **repo-root `.env`** (shared `JWT_SECRET` /
`AGENT_SERVICE_TOKEN`). Optional Agent 4 tuning keys are listed in
`.env.example` and in [Configuration](#configuration) — all have safe defaults,
so the service runs with none of them set.

## Authentication

Unchanged from before, and enforced on **every** endpoint including `/audit/*`:

- `Authorization: Bearer <user JWT issued by Agent 1>` — a caller may only
  decide for their own `user_id` (IDOR guard).
- `Authorization: Bearer <AGENT_SERVICE_TOKEN>` or `X-Service-Token: <AGENT_SERVICE_TOKEN>`
  for inter-agent calls.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/decision/recommend` | The decision. Query param `llm_polish=false` (default) — see Feature 3. |
| `POST` | `/decision/analyze` | Diagnostic view (unchanged). |
| `POST` | `/decision/alternatives` | Runner-ups (unchanged). |
| `GET` | `/decision/health`, `/health` | Liveness probes. |
| `GET` | `/audit` | **new** — paginated decision audit log, service token only. |
| `GET` | `/audit/{decision_id}` | **new** — one audit row, service token only. |

## Request

Every field of the existing `DecisionRequest` contract is unchanged. One
optional field was added:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `reoptimization_round` | `int` (0–20) | `0` | How many times this session has already been re-planned. At `MAX_REOPTIMIZATION_ROUNDS` Agent 4 stops rejecting and returns its best available answer. Omitting it is identical to today's behaviour. |

## Response — what is new

All pre-existing fields (`request_id`, `decision`, `selected_combination_id`,
`strategy`, `outfit`, `budget`, `purchase_summary`, `metrics`, `alternatives`,
`unresolved_requirements`, `explanation`, `validation_issues`, `currency`) keep
their names, types and meaning. Everything below is **additive and optional** —
a caller that ignores it is unaffected.

| Field | Type | Empty/`null` when | Feature |
|---|---|---|---|
| `score_breakdown` | array of ranked candidates | no candidate survived the hard constraints | 1 |
| `reason_codes` | array of enum | the call did end in a complete outfit | 2 |
| `candidate_rejections` | array | every candidate was acceptable | 2 |
| `excluded_product_ids` | array of product ids | nothing was rejected | 2 |
| `suggested_action` | enum or `null` | nothing needs doing | 2 |
| `reoptimization_round` | `int` echo | never (defaults `0`) | 2 |
| `retry_limit_reached` | `bool` | `false` until the cap | 2 |
| `retry_limit_reason` | `string` or `null` | `null` unless the cap was hit | 2 |
| `explanation_source` | `"template"` \| `"llm"` | only if decoration could not run | 3 |
| `explanation_verified` | `bool` | — | 3 |
| `verification_issues` | array of coded strings | explanation passed | 3 |
| `counterfactuals` | array (max 3) | nothing meaningful to report | 4 |
| `decision_id` | `dec_<16 hex>` or `null` | auditing disabled or the write failed | 5 |

### Feature 1 — score breakdown

`score_breakdown` reports the chosen outfit (`rank: 1, selected: true`) plus up
to `MAX_BREAKDOWN_CANDIDATES` runner-ups, each through five normalised
sub-scores, the weights actually used, and both the new weighted
`overall_score` and the pre-existing `decision_score` side by side — ranking is
still driven by `decision_score`, so nothing is silently re-based.

Sub-scores: `colour_harmony`, `formality_match`, `occasion_fit`, `budget_fit`,
`constraint_satisfaction`. Weights come from `SB_W_*` (must sum to 1.0; the
service refuses to start otherwise) and are versioned by
`SCORE_WEIGHTS_VERSION`, which is also stamped on every breakdown entry and
audit row.

**Scoring never reads gender, body type, skin tone or brand prestige.** The
inputs are prices, availability, category/type match, upstream match scores and
the planner's ceiling.

### Feature 2 — structured rejection and the retry limit

`reason_codes` uses exactly this enum: `STYLE_CLASH`,
`MISSING_REQUIRED_CATEGORY`, `OVER_BUDGET`, `CONSTRAINT_VIOLATION`,
`LOW_CONFIDENCE`, `INCOMPLETE_OUTFIT`.

- `candidate_rejections` — one entry per candidate Agent 4 could not offer,
  with its codes, a human `detail`, and the product ids it contained.
- `excluded_product_ids` — those products, deduped and capped at
  `MAX_EXCLUDED_PRODUCT_IDS`, ready to feed into Agent 2 / Agent 3's existing
  `excluded_product_ids` request field.
- `suggested_action` — one of `retry_with_exclusions`, `increase_budget`,
  `relax_constraints`, `accept_best_available`, `request_clarification`.
- Retry cap: when `reoptimization_round >= MAX_REOPTIMIZATION_ROUNDS` (default
  3) Agent 4 does **not** reject again. It returns the best available candidate
  — preferring a zero-purchase (buy-nothing) option if one exists — with
  confidence forced to `FORCED_LOW_CONFIDENCE_SCORE` (so the level is Low),
  `retry_limit_reached: true`, a `retry_limit_reason`, the reason codes from the
  earlier rounds kept visible, and `suggested_action: accept_best_available`.
  This path can only trigger on a call that would otherwise have answered
  "no suitable outfit".

### Feature 3 — explanation faithfulness check

Both the deterministic template and any Gemini-polished text are checked against
the supplied data before being returned:

- every amount quoted must exist in the request (including per-option totals and
  budget-remaining arithmetic — "leaving USD x" is recomputed),
- every product id and quoted name must exist,
- every colour named must belong to an item actually in the outfit,
- no invented store, no discount/percentage/voucher claims.

`explanation_source` says which text is in `explanation`. If the LLM version
fails the check it is **discarded and the template is used instead**
(`explanation_source: "template"`, and the problems listed in
`verification_issues`, capped at `MAX_VERIFICATION_ISSUES`). The decision itself
is never affected by the LLM — Gemini only re-words. With no API key, or
`LLM_PROVIDER=mock`, everything above still runs identically.

### Feature 4 — counterfactuals

Pure deterministic re-scoring; the LLM is never involved and no probe result is
ever returned as a recommendation. Up to `MAX_COUNTERFACTUALS` entries, each
with machine fields (`kind`, `field`, `old_value`, `new_value`,
`resulting_winner`, `sub_score`) and a human `sentence`:

- `budget_increase` — the smallest ceiling raise (searched at real option
  totals, up to `COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD` above the stated
  ceiling) that hands the win to a runner-up.
- `no_budget_change` — the honest negative: nothing within that bound flips the
  answer.
- `item_swap` — one single-product substitution, probed at most
  `COUNTERFACTUAL_MAX_SWAP_PROBES` times, that flips the decision.
- `sub_score` — which reported axis explains the flip.

`counterfactuals` is `[]` when nothing would meaningfully change the result.

### Feature 5 — decision audit log

Every `/decision/recommend` call records one SQLite row at `AUDIT_DB_PATH`
(default `agents/agent4_decision/data/audit.db`, which is git-ignored). The
table stores:

`decision_id`, `recorded_at`, `request_id`, `input_sha256`, `candidate_ids`,
`score_breakdowns`, `weights_version`, `chosen_combination_id`,
`decision_status`, `reject_reason_codes`, `confidence_score`,
`confidence_level`, `explanation_source`, `explanation_verified`,
`reoptimization_round`.

Privacy properties:

- the **request is stored as a SHA-256 hash of its canonical JSON, never as
  content** — no user text, no item descriptions, no images, no PII;
- `decision_id` is derived from that hash (`"dec_" + sha256[:16]`), so the same
  input maps to the same row and responses stay byte-for-byte comparable;
- writes are best-effort: an audit failure logs the exception *type* only and
  never changes or breaks the decision a user is waiting for;
- read endpoints are service-token only (a user JWT gets `403`), paginated
  newest-first (`?page=1&page_size=20`, max `AUDIT_MAX_PAGE_SIZE`), `404` on an
  unknown id, `503` if the store is unreadable.

## Example: `POST /decision/recommend`

Request — the three upstream payloads are the unchanged contract objects; the
only new key is `reoptimization_round`.

```json
{
  "request_id": "REQ-TEST-0001",
  "agent1_output": { "...": "validated Agent 1 contract, unchanged" },
  "budget_response": {
    "request_id": "REQ-TEST-0001",
    "status": "within_budget",
    "budget_ceiling": 200.0,
    "budget_source": "user_stated",
    "recommended_option_id": "OPT-FULL",
    "options": [
      { "combination_id": "OPT-FULL",    "strategy": "top_match",        "total": 100.0, "is_within_budget": true },
      { "combination_id": "OPT-ALT",     "strategy": "best_value",       "total": 190.0, "is_within_budget": true },
      { "combination_id": "OPT-PREMIUM", "strategy": "minimal_purchase", "total": 260.0, "is_within_budget": false }
    ]
  },
  "retrieval_by_category": { "top": { "...": "Agent 2 response" }, "footwear": { "...": "Agent 2 response" } },
  "user_id": null,
  "prefer_minimal_purchases": true,
  "reoptimization_round": 0
}
```

Response (real output of this service in `LLM_PROVIDER=mock`; `options[]` and
`outfit[]` abbreviated for reading, every Agent 4-computed value verbatim):

```json
{
  "request_id": "REQ-TEST-0001",
  "decision": { "status": "complete", "confidence_score": 0.91, "confidence_level": "high" },
  "selected_combination_id": "OPT-FULL",
  "strategy": "top_match",
  "outfit": [
    { "source": "purchase", "item_id": "P-TOP-01", "category": "top", "name": "White cotton blouse", "price_usd": 45.0, "role": "Completes the top requirement" },
    { "source": "purchase", "item_id": "P-SHOE-01", "category": "footwear", "name": "Brown suede loafer", "price_usd": 55.0, "role": "Completes the footwear requirement" }
  ],
  "budget": { "maximum_usd": 200.0, "additional_cost_usd": 100.0, "remaining_usd": 100.0, "within_budget": true },
  "purchase_summary": { "purchase_count": 2, "existing_items_used": 0 },
  "metrics": { "occasion_fit": 0.9, "style_fit": 0.9, "colour_fit": 0.9, "wardrobe_reuse": 0.0,
               "retrieval_relevance": 0.9, "budget_efficiency": 0.8, "purchase_count": 2,
               "within_budget": true, "is_complete": true, "decision_score": 0.755 },
  "alternatives": [
    { "combination_id": "OPT-ALT", "strategy": "best_value", "total_cost_usd": 190.0,
      "within_budget": true, "decision_score": 0.6438, "reason": "also fits your constraints" }
  ],
  "unresolved_requirements": [],
  "explanation": "Selected “Option OPT-FULL”. New items: White cotton blouse (USD 45.00, Test Retailer); Brown suede loafer (USD 55.00, Test Retailer). The total additional cost is USD 100.00 against your USD 200.00 budget, leaving USD 100.00 to spare. …",
  "validation_issues": [],
  "currency": "USD",

  "score_breakdown": [
    {
      "combination_id": "OPT-FULL", "rank": 1, "selected": true,
      "sub_scores": { "colour_harmony": 0.875, "formality_match": 0.65, "occasion_fit": 0.9,
                      "budget_fit": 0.9, "constraint_satisfaction": 1.0 },
      "weights": { "colour_harmony": 0.25, "formality_match": 0.2, "occasion_fit": 0.2,
                   "budget_fit": 0.15, "constraint_satisfaction": 0.2 },
      "weights_version": "breakdown-v1", "overall_score": 0.8638, "decision_score": 0.755
    },
    {
      "combination_id": "OPT-ALT", "rank": 2, "selected": false,
      "sub_scores": { "colour_harmony": 0.8, "formality_match": 0.8, "occasion_fit": 0.825,
                      "budget_fit": 0.75, "constraint_satisfaction": 1.0 },
      "weights": { "colour_harmony": 0.25, "formality_match": 0.2, "occasion_fit": 0.2,
                   "budget_fit": 0.15, "constraint_satisfaction": 0.2 },
      "weights_version": "breakdown-v1", "overall_score": 0.8375, "decision_score": 0.6438
    }
  ],

  "reason_codes": [],
  "candidate_rejections": [
    {
      "combination_id": "OPT-PREMIUM", "name": "Option OPT-PREMIUM",
      "reason_codes": ["OVER_BUDGET"],
      "detail": "Over budget (budget feasibility comes from the purchase planner)",
      "product_ids": ["P-TOP-03", "P-SHOE-03"]
    }
  ],
  "excluded_product_ids": ["P-TOP-03", "P-SHOE-03"],
  "suggested_action": "retry_with_exclusions",
  "reoptimization_round": 0,
  "retry_limit_reached": false,
  "retry_limit_reason": null,

  "explanation_source": "template",
  "explanation_verified": true,
  "verification_issues": [],

  "counterfactuals": [
    {
      "kind": "budget_increase", "field": "budget_response.budget_ceiling",
      "old_value": 200.0, "new_value": 260.0, "resulting_winner": "OPT-PREMIUM",
      "sub_score": "budget_fit",
      "sentence": "Raising the budget from USD 200.00 to USD 260.00 would make OPT-PREMIUM the better answer than OPT-FULL. The gap is widest on budget fit (0.65 against 0.90)."
    },
    {
      "kind": "item_swap", "field": "options[OPT-FULL].products[P-TOP-01]",
      "old_value": "P-TOP-01", "new_value": "P-TOP-03", "resulting_winner": "OPT-ALT",
      "sub_score": "budget_fit",
      "sentence": "Swapping P-TOP-01 for P-TOP-03 in OPT-FULL would hand the decision to OPT-ALT. The deciding axis is budget fit (0.75 against 0.39)."
    }
  ],

  "decision_id": "dec_8d5a5ab0b799bfd4"
}
```

Read the audit row back:

```bash
curl -H "X-Service-Token: $AGENT_SERVICE_TOKEN" \
  "http://localhost:8004/audit/dec_8d5a5ab0b799bfd4"
curl -H "X-Service-Token: $AGENT_SERVICE_TOKEN" \
  "http://localhost:8004/audit?page=1&page_size=20"
```

## Configuration

All keys live in `app/core/config.py`, are env-overridable, are non-secret, and
are listed in the repo-root `.env.example`. The service fails at startup — with
a clear message, not a silent fallback — if a combination is unusable (weights
not summing to 1, a forced-confidence value at or above the Low threshold, a
non-positive cap, a bias threshold outside 0–1).

| Key | Default | Used by |
|---|---|---|
| `SB_W_COLOUR_HARMONY` / `SB_W_FORMALITY_MATCH` / `SB_W_OCCASION_FIT` / `SB_W_BUDGET_FIT` / `SB_W_CONSTRAINT_SAT` | `0.25 / 0.20 / 0.20 / 0.15 / 0.20` | F1 |
| `MAX_BREAKDOWN_CANDIDATES` | `4` | F1 |
| `SCORE_WEIGHTS_VERSION` | `breakdown-v1` | F1, F5 |
| `MAX_REOPTIMIZATION_ROUNDS` | `3` | F2 |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | F2 |
| `FORCED_LOW_CONFIDENCE_SCORE` | `0.40` | F2 |
| `MAX_EXCLUDED_PRODUCT_IDS` | `50` | F2 |
| `MAX_VERIFICATION_ISSUES` / `VERIFICATION_ISSUE_TEXT_LIMIT` | `10 / 60` | F3 |
| `MAX_COUNTERFACTUALS` | `3` | F4 |
| `COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD` | `500.0` | F4 |
| `COUNTERFACTUAL_MAX_SWAP_PROBES` | `12` | F4 |
| `AUDIT_ENABLED` | `true` | F5 |
| `AUDIT_DB_PATH` | `agents/agent4_decision/data/audit.db` | F5 |
| `AUDIT_MAX_PAGE_SIZE` / `AUDIT_DEFAULT_PAGE_SIZE` | `100 / 20` | F5 |
| `AUDIT_LOCK_TIMEOUT_SECONDS` | `5.0` | F5 |
| `BIAS_FLAG_THRESHOLD` | `0.05` | F5 |

The pre-existing ranking weights (`W_OCCASION`, `W_STYLE`, `W_COLOUR`,
`W_WARDROBE_REUSE`, `W_RELEVANCE`, `W_BUDGET`) are untouched and still drive
`metrics.decision_score`.

## Tests

Unit and integration tests need no other agent running and no API key
(`conftest.py` forces `LLM_PROVIDER=mock` and a temp audit file).

```bash
cd agents/agent4_decision
PYTHONPATH=/path/to/repo .venv/bin/python -m pytest tests -q        # Windows: .venv\Scripts\python.exe
```

Coverage by feature: `test_score_breakdown.py` (F1), `test_rejection.py` (F2),
`test_explanation_verification.py` (F3), `test_counterfactuals.py` (F4),
`test_audit_log.py` + `test_bias_harness.py` (F5), plus the pre-existing
`test_recommend.py`, `test_hard_constraints.py`, `test_analysis_endpoints.py`,
`test_security.py`, `test_type_checks.py`, which were not modified.

## Bias harness

`tests/bias/run_bias_harness.py` drives the live endpoint with matched profile
pairs — each pair changes exactly **one** input attribute — and compares chosen
combination, covered categories, decision score, confidence and rejection rate.

- `neutral` pairs carry no decision-relevant information (gender-coded wording,
  body-size-coded collection labels, skin-tone-coded colour wording, cultural
  and religious occasion names, a stated budget the planner never confirmed).
  Any difference is a **flag** and the harness exits `1`.
- `signal` pairs are genuine styling requirements (garment type, style and
  colour vocabulary, the planner's ceiling); a difference there is correct and
  is reported unflagged.

```bash
cd agents/agent4_decision
PYTHONPATH=/path/to/repo .venv/bin/python tests/bias/run_bias_harness.py
```

Output: a console summary and a Markdown report at
`docs/responsible_ai/agent4_bias_report.md`. The report quotes no request
content, and the harness changes no code — it measures and reports only.

## Design rules this service follows

1. Additive-only contract: existing field names, types and semantics are
   unchanged; new request fields are optional with safe defaults; new models are
   local to `app/schemas/agent4_extensions.py`.
2. Deterministic core: selection, scoring, rejection, counterfactuals and
   verification are plain Python and fully reproducible; the LLM is optional
   wording polish and can only ever be discarded, never trusted.
3. Untrusted data: product names/descriptions and user text are treated as data
   — they are validated by Pydantic v2 and quoted back only after the
   faithfulness check; they are never interpolated as instructions. Errors are
   masked (`500` returns a generic detail; stack traces go to logs, PII-scrubbed).
4. No protected attribute enters scoring or ranking.
5. No magic numbers: every weight, threshold and cap is in the config module.

## Fixed defect (pre-existing, corrected on request)

`app/services/explanation_service.py:103` compared the runner-up price with an
inverted ternary, so the trade-off sentence could read "USD 90.00 **cheaper**"
when the alternative was in fact more expensive. The amount was always real —
Feature 3's verifier checks amounts, ids, names, colours and stores, not
comparative adjectives — which is why the wording slipped through.

Now the diff is computed as `runner-up total − chosen total`, so a positive
difference reads "more expensive" and a negative one reads "cheaper".
`tests/test_recommend.py::test_runner_up_cost_direction_is_named_correctly`
pins both directions: the higher-relevance option wins regardless of price, so
the same pair of prices exercises each adjective. Nothing else in the
explanation template changed, and the example sentence below is real output of
the fixed code (`mock` provider, 190.00 against 100.00):

> The next-best alternative (“Option OPT-ALT”) is USD 90.00 more expensive but
> matched your style and colour preferences less well.

## Proposed contract additions (for the contract owners)

Nothing in `docs/api/api-contracts.md` or `shared/schemas/agent4_schemas.py`
was edited. If the team wants these fields to become part of the shared Agent 4
contract, this is the diff to adopt:

**Request** — `reoptimization_round: int = 0` (0–20).

**Response** — `score_breakdown: List[ScoreBreakdown]`, `reason_codes:
List[RejectReasonCode]`, `candidate_rejections: List[CandidateRejection]`,
`excluded_product_ids: List[str]`, `suggested_action: Optional[SuggestedAction]`,
`reoptimization_round: int`, `retry_limit_reached: bool`, `retry_limit_reason:
Optional[str]`, `explanation_source: Optional[str]`, `explanation_verified:
Optional[bool]`, `verification_issues: List[str]`, `counterfactuals:
List[Counterfactual]`, `decision_id: Optional[str]` — all optional with empty
defaults, so adopting them is non-breaking for every existing caller.

**Enums** — `RejectReasonCode` (`STYLE_CLASH`, `MISSING_REQUIRED_CATEGORY`,
`OVER_BUDGET`, `CONSTRAINT_VIOLATION`, `LOW_CONFIDENCE`, `INCOMPLETE_OUTFIT`),
`SuggestedAction` (`retry_with_exclusions`, `increase_budget`,
`relax_constraints`, `accept_best_available`, `request_clarification`),
`CounterfactualKind` (`budget_increase`, `no_budget_change`, `item_swap`,
`sub_score_flip`).

**New service-to-service surface** — `GET /audit` and `GET /audit/{decision_id}`,
restricted to `AGENT_SERVICE_TOKEN` callers.
