# Responsible AI Notes

Living document — add entries as each agent is built, don't leave this for the
end of the project.

## Transparency & explainability
- Agent 4 must return a human-readable `explanation` field with every recommendation.
- Agent 4 must return a `confidence` score, not present results as certain.

## Fairness / bias test log
Track controlled test profiles here as they're run (owned primarily by the
Responsible AI specialization, but every agent should log relevant results).

| Date | Test profile | Agent tested | Result | Notes |
|---|---|---|---|---|
| | | | | |

## Data protection
- Image uploads: user must be informed images are stored/processed (consent notice).
- Data minimization: only collect fields actually used by an agent.
- No PII in logs — logs should reference request IDs, not raw user data.

## Known limitations (update as discovered)
-
