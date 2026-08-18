# Contributing to FASHORA

Kept deliberately simple — four people, one semester, no need for enterprise git flow.

## Branching strategy

- `main` — protected. Always in a working, demo-able state. No direct pushes.
- One feature branch per unit of work, named:
  ```
  <agent-or-area>/<short-description>
  ```
  Examples:
  - `agent2/bm25-baseline`
  - `agent1/clip-classification`
  - `orchestrator/feedback-loop`
  - `docs/api-contracts`

## Workflow

1. Pull latest `main` before starting new work.
2. Create your feature branch from `main`.
3. Commit in small, meaningful chunks. Commit message format:
   ```
   <area>: <what changed>
   ```
   e.g. `agent2: add BM25 baseline retrieval`
4. Open a Pull Request into `main` when your piece works locally.
5. **At least one other member reviews before merging** — this is also what the
   viva checks when it asks about individual contribution, so don't skip it.
6. Squash-merge or merge normally (team's choice) — just be consistent.

## Branch protection (set up in GitHub repo Settings → Branches)

- Require a pull request before merging to `main`.
- Require at least 1 approval.
- Do not allow force-pushes to `main`.

## Code style

- Python: keep it readable; `black` for formatting and `flake8` for linting are
  recommended but not mandatory for a course project.
- Every new agent endpoint needs a Pydantic model for its request and response —
  no raw untyped dicts crossing agent boundaries.

## Secrets

- Never commit `.env`, API keys, or database credentials.
- `.env.example` shows the required variable names with placeholder values only.
- If a secret is committed by accident, rotate it immediately, don't just delete
  the file in a later commit (it stays in git history).
