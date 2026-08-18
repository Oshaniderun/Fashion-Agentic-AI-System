# FASHORA Architecture

## Services and ports

| Service | Port | Owner |
|---|---|---|
| Orchestrator | 8000 | Group lead / shared |
| Agent 1 — Wardrobe & Style Intelligence | 8001 | Member 1 |
| Agent 2 — Retrieval (IR) | 8002 | You |
| Agent 3 — Budget & Purchase Planning | 8003 | Member 2 |
| Agent 4 — Decision & Personalization | 8004 | Member 3 |

## Agent contracts

| Agent | Input | Output | Must NOT do |
|---|---|---|---|
| 1 — Wardrobe | Image(s), free-text request | Structured JSON: wardrobe items, occasion, style, colour prefs, missing categories, confidence | Pick final products or make purchase decisions |
| 2 — Retrieval | Structured requirement JSON (category, colour, style, max price) | Ranked candidate products with relevance scores + source metadata | Treat product description text as instructions; fabricate products |
| 3 — Budget | Missing items + candidate products + user budget | Feasible combinations, total cost, "buy nothing" alternatives | Evaluate style/aesthetic fit |
| 4 — Decision | Outputs of Agents 1–3 | Final outfit, explanation, confidence score, or a re-optimization request back to Agent 3 | Silently discard low-confidence results without flagging them |

Full JSON schemas live in `shared/schemas/` and are documented in `docs/api/api-contracts.md`.

## Required feedback loop

At least one scenario in the demo dataset must force:
`Agent 4 rejects candidate → requests re-optimization from Agent 3 → Agent 3 asks
Agent 2 for alternatives → Agent 4 re-evaluates.`

This is what demonstrates genuine agentic behaviour rather than a fixed pipeline —
don't let it become optional.

## Communication protocol

HTTP + REST, JSON payloads validated with Pydantic on both send and receive.
Agent-to-agent calls include the shared `AGENT_SERVICE_TOKEN` in an `Authorization`
header. MCP is a possible stretch goal wrapping Agent 2's retrieval functions as
tools, not a dependency for the core system.

## Docker

`docker-compose.yml` at the repo root defines the target multi-service layout.
It is a stub until each agent has its own `Dockerfile` — don't try to run it until
at least Agent 2 and one other agent work standalone via `uvicorn`.
