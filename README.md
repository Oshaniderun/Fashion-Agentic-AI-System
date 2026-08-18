# Fashion-Agentic-AI-System (FASHORA)

IT3041 (Information Retrieval and Web Analytics) group project.

FASHORA analyses a user's existing wardrobe, occasion, style and budget, retrieves
suitable products, checks affordability, and produces an explainable, personalized
outfit recommendation — using four cooperating agents rather than a single chatbot call.

## Problem
Fashion decisions are time-consuming and expensive when they ignore what a person
already owns. FASHORA reduces unnecessary purchases by reasoning over the *existing*
wardrobe first, and only recommending new items when genuinely needed.

## Architecture

```
USER (image + text + occasion + budget)
        │
        ▼
API Gateway (JWT auth, rate limiting, validation)
        │
        ▼
Orchestrator ── session state, retry logic, feedback-loop routing
        │
   ┌────┼────────────────┐
   ▼    ▼                ▼
Agent 1 Agent 2        Agent 3
Wardrobe Retrieval     Budget
   │       │                │
   └───────┴────────┬───────┘
                     ▼
                  Agent 4
              Decision + Explanation
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
  Final Recommendation     (if rejected) → back to
  + Explanation             Agent 3 for re-optimization
```

Full notes: [`docs/architecture/architecture.md`](docs/architecture/architecture.md).
API contracts: [`docs/api/api-contracts.md`](docs/api/api-contracts.md).

## Repository structure

```
Fashion-Agentic-AI-System/
├── agents/
│   ├── agent1_wardrobe/     # Image + NLP analysis of what the user has/needs
│   ├── agent2_retrieval/    # Product search & ranking (IR) — includes its own data/
│   ├── agent3_budget/       # Budget optimization, "buy nothing" mode
│   └── agent4_decision/     # Final selection, explanation, confidence
├── orchestrator/            # Routes between agents, owns session state, drives the feedback loop
├── shared/                  # Common Pydantic schemas, constants, utils used by every agent
├── frontend/                # React UI
├── docs/
│   ├── architecture/        # System design, agent contracts, ports
│   ├── api/                 # Request/response schemas per endpoint
│   ├── responsible_ai/      # Bias test log, transparency, data protection notes
│   ├── security/            # Auth, sanitization, threat notes — feeds the individual audit
│   └── commercialization/   # Pricing, target market, deployment plan
├── tests/
│   ├── integration/         # Multi-agent flows within the same process/mocked calls
│   └── end_to_end/          # Full pipeline through the orchestrator, real services
├── .gitignore
├── .env.example
├── docker-compose.yml
└── LICENSE
```

Each agent under `agents/` has its own `app/`, `tests/`, `requirements.txt`, and README
with purpose, inputs/outputs, and how to run it.

## Setup

1. Clone the repo and copy the environment template:
   ```bash
   git clone https://github.com/<your-org>/Fashion-Agentic-AI-System.git
   cd Fashion-Agentic-AI-System
   cp .env.example .env
   ```
2. Fill in `.env` with the shared LLM API key, database URL, and JWT secret (ask the
   group lead for dev values — never commit real secrets).
3. Each agent has its own virtual environment and `requirements.txt`:
   ```bash
   cd agents/agent2_retrieval
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8002
   ```
4. Repeat for whichever agents you need running locally. Ports are fixed per agent
   (see `docs/architecture/architecture.md`).

## Tech stack
- **Backend:** Python, FastAPI (one service per agent + orchestrator)
- **LLM:** single shared provider (see `.env.example`)
- **NLP:** spaCy + LLM structured extraction
- **CV:** CLIP / FashionCLIP
- **IR:** BM25 (rank-bm25) + Sentence-Transformers embeddings + Chroma
- **Database:** PostgreSQL (SQLite acceptable for local dev)
- **Auth:** JWT (user-facing) + shared service token (agent-to-agent)
- **Frontend:** React

## Contributors

| Name | Role | Primary Agent | Security Specialization (individual assignment) |
|---|---|---|---|
| _Member 1_ | | Agent 1 — Wardrobe | Prompt Injection / Jailbreak |
| _You_ | Group Lead | Agent 2 — Retrieval | Information Retrieval & Security |
| _Member 2_ | | Agent 3 — Budget + Auth | Privacy & Data Leakage |
| _Member 3_ | | Agent 4 — Decision | Responsible AI & Bias |

## Contributing
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branching strategy, PR process, and
commit conventions.
