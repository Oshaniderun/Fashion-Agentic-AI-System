# Security Notes

Tracks security controls actually implemented (not aspirational). This is what
each member points to when justifying their design during the group viva, and
what feeds directly into the later individual security audit — keep it accurate,
not optimistic.

## Baseline controls checklist

| Control | Status | Owner | Notes |
|---|---|---|---|
| JWT user authentication | ☐ | Member 2 | |
| Agent-to-agent service token | ☐ | Group lead / shared | See `AGENT_SERVICE_TOKEN` in `.env.example` |
| Pydantic input validation on every endpoint | ☐ | All agents | No raw untyped dicts crossing boundaries |
| Input sanitization before any LLM call | ☐ | Agents 1, 2, 3, 4 | Especially retrieved product text (Agent 2) |
| Password hashing (bcrypt/argon2) | ☐ | Member 2 | |
| Rate limiting | ☐ | Orchestrator / API gateway | Basic per-user limit is enough for a prototype |
| HTTPS in deployment | ☐ | Deployment | Can be TLS-terminated at a reverse proxy |
| Secrets never committed | ✅ (by convention) | All | `.env` is gitignored; rotate immediately if leaked |
| Logging without PII | ☐ | All agents | Request IDs, not raw user data |

## Known deliberate attack surfaces (for the individual audit — not vulnerabilities to "fix away")

- **Agent 2 retrieved content is untrusted.** Product descriptions come from an
  external/simulated source and must never be treated as instructions by any LLM
  call downstream. This is the basis for the indirect prompt injection test case.
- **Agent 1 accepts free-text + images from the user directly** — the natural
  surface for direct prompt injection / jailbreak testing.
- **Wardrobe and recommendation data is per-user** — the natural surface for IDOR/
  cross-user access testing (Privacy & Data Leakage specialization).

Do not patch these away preemptively — document them here so they're testable
later, but keep basic input validation and auth in place so testing them isn't
trivial for the wrong reasons (e.g. a completely open endpoint isn't an
interesting "attack," it's just a missing control).
