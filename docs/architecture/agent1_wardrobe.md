# Agent 1 — Style & Wardrobe Intelligence Architecture

## Role in FASHORA

Agent 1 is the wardrobe and request-understanding service. It produces a validated JSON contract for Agents 2–4 and never performs product search, budget optimization, or final outfit purchase decisions.

## Processing pipeline

1. **Auth** — JWT user sessions; wardrobe rows scoped by `user_id`
2. **Image path** — validate magic bytes / size → store under `uploads/` → colour + pattern analyzers → optional CLIP → draft attributes for user confirmation
3. **NLP path** — prompt guard → synonym normalization → deterministic extraction (+ optional LLM structured repair) → Pydantic `UserRequirements`
4. **Outfit rules** — occasion/style → required & optional categories (`outfit_requirements.py`)
5. **Matching** — select owned items that fit requirements
6. **Missing items** — set difference → `Agent2SearchRequirement` handoff
7. **Compatibility** — colour harmony, style/formality distance, occasion suitability + explanation
8. **Contract** — `Agent1OutputContract` with `request_id` correlation

## Dual-engine design

| Layer | Default (CPU laptop) | Optional enhanced |
|---|---|---|
| Vision | Pillow + K-Means + texture heuristics | CLIP / FashionCLIP (`VISION_MODEL_BACKEND=clip`) |
| NLP | Regex + ontology normalizer | OpenAI / Anthropic structured extractor |

Both are behind abstract interfaces so models can be swapped without rewriting API routes.

## Security

- Prompt injection detection / sanitization (`prompt_guard.py`)
- Image content validation, path sanitization, upload size limits
- bcrypt passwords, JWT auth, CORS allowlist
- Security Lab UI hits `/api/security/test-prompt` with preset red-team payloads

## Ports

| Service | Port |
|---|---|
| Agent 1 FastAPI | 8001 |
| Frontend (Vite) | 5173 |

## Key contracts

Shared source of truth: `shared/schemas/agent1_schemas.py`

- `UserRequirements`
- `OutfitRequirements`
- `Agent1OutputContract`
- `Agent2SearchRequirement`
