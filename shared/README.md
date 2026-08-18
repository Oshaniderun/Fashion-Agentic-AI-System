# Shared

Common code used by more than one agent:
- `schemas/` — Pydantic models for every agent's request/response contracts
- `utils/` — shared helpers (e.g. auth token verification, logging setup)
- `constants.py` — shared enums/constants (e.g. clothing categories, occasion types)

Nothing agent-specific belongs here. If only one agent uses it, it lives in that
agent's own folder.

Kept `constants.py` as a single file rather than a folder — split it into
multiple files only if it genuinely grows past a couple hundred lines.
