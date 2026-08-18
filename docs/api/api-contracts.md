# API Contracts

Single source of truth for the JSON shape every agent sends and receives.
Update this whenever a schema changes — other members build against this,
not against your code.

## Status

| Agent | Endpoint | Request schema defined? | Response schema defined? |
|---|---|---|---|
| 1 — Wardrobe | `POST /analyze-wardrobe` | ☐ | ☐ |
| 2 — Retrieval | `POST /retrieve-products` | ☐ | ☐ |
| 3 — Budget | `POST /optimize-budget` | ☐ | ☐ |
| 4 — Decision | `POST /decide-outfit` | ☐ | ☐ |

Keep the actual Pydantic models in `shared/schemas/` — this file documents them in
plain language for people who haven't read the code.

---

## Agent 1 — `POST /analyze-wardrobe`
_Request / Response schema: TBD_

## Agent 2 — `POST /retrieve-products`
_Request / Response schema: TBD — this is next on our list_

## Agent 3 — `POST /optimize-budget`
_Request / Response schema: TBD_

## Agent 4 — `POST /decide-outfit`
_Request / Response schema: TBD_
