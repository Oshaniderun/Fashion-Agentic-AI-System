# Orchestrator

Owns session state, routes requests between agents, and drives the required
feedback loop (Agent 4 → Agent 3 → Agent 2 re-optimization).

## Responsibilities
- Receive the initial user request from the API gateway
- Call Agent 1 first, then Agent 2/3, then Agent 4
- If Agent 4 requests re-optimization, route back to Agent 3
- Return the final recommendation to the frontend
- Should NOT contain business logic that belongs to a specific agent

## Run
```
uvicorn app.main:app --reload --port 8000
```
(To be implemented.)
