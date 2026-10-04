"""
Configuration for the FASHORA Outfit Decision service (Agent 4).

Same conventions as Agents 1-3:
- pydantic-settings reads the repo-root .env, so the canonical JWT_SECRET and
  AGENT_SERVICE_TOKEN are shared system-wide.
- Agent 4 consumes validated upstream payloads over HTTP/JSON and never touches
  the shared database. Its only persistence is a local, hash-keyed decision
  audit file (AUDIT_DB_PATH) that stores no request content.
- Every tuning knob lives here and is env-overridable; nothing in the services
  hardcodes a weight, threshold or limit.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: agents/agent4_decision/app/core/config.py -> four levels up.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    APP_NAME: str = "FASHORA Outfit Decision Service"
    VERSION: str = "1.0.0"
    # SERVICE_HOST/SERVICE_PORT avoid the generic HOST/PORT keys in the root
    # .env, which belong to Agent 1 (8001). Agents 2/3 use 8002/8003.
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8004
    ENVIRONMENT: str = "development"

    # ── Security / Authentication (root .env supplies the real values) ─────
    JWT_SECRET: str = "fashora_agent1_dev_jwt_secret_key_2026_secure"
    JWT_ALGORITHM: str = "HS256"
    AGENT_SERVICE_TOKEN: str = "fashora_shared_service_token_2026"

    # ── Currency (USD everywhere in this repo) ─────────────────────────────
    CURRENCY: str = "USD"

    # ── Decision tuning (deterministic scoring weights) ────────────────────
    W_OCCASION: float = 0.15
    W_STYLE: float = 0.20
    W_COLOUR: float = 0.20
    W_WARDROBE_REUSE: float = 0.15
    W_RELEVANCE: float = 0.20
    W_BUDGET: float = 0.10

    # ── Feature 1: score-breakdown weights (explain the five decision axes) ─
    # These are SEPARATE from W_* above: W_* still drives ranking (unchanged
    # behaviour), while these re-project the same signals onto the five
    # reported sub-scores. They must sum to 1.0 — validated at startup.
    SB_W_COLOUR_HARMONY: float = 0.25
    SB_W_FORMALITY_MATCH: float = 0.20
    SB_W_OCCASION_FIT: float = 0.20
    SB_W_BUDGET_FIT: float = 0.15
    SB_W_CONSTRAINT_SAT: float = 0.20
    # How many candidates the breakdown is reported for (chosen + runner-ups).
    MAX_BREAKDOWN_CANDIDATES: int = 4
    # Bumped whenever the default weights change; recorded on every audit row.
    SCORE_WEIGHTS_VERSION: str = "breakdown-v1"

    # ── Feature 2: structured rejection + re-optimization cap ───────────────
    MAX_REOPTIMIZATION_ROUNDS: int = 3
    LOW_CONFIDENCE_THRESHOLD: float = 0.50
    MAX_EXCLUDED_PRODUCT_IDS: int = 50
    # Confidence reported when the retry cap forces a "return the best we have"
    # answer. Must stay below LOW_CONFIDENCE_THRESHOLD so the level is Low.
    FORCED_LOW_CONFIDENCE_SCORE: float = 0.40

    # ── Feature 3: explanation faithfulness verification ────────────────────
    MAX_VERIFICATION_ISSUES: int = 10
    VERIFICATION_ISSUE_TEXT_LIMIT: int = 60

    # ── Feature 4: counterfactual search bounds ─────────────────────────────
    MAX_COUNTERFACTUALS: int = 3
    # How far above the stated ceiling the budget probe is allowed to look.
    COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD: float = 500.0
    # Cap on single-substitution probes per decision (search cost, not accuracy).
    COUNTERFACTUAL_MAX_SWAP_PROBES: int = 12

    # ── Feature 5: audit log + bias harness ─────────────────────────────────
    AUDIT_ENABLED: bool = True
    AUDIT_DB_PATH: str = ""  # empty -> repo-relative default resolved below
    AUDIT_MAX_PAGE_SIZE: int = 100
    AUDIT_DEFAULT_PAGE_SIZE: int = 20
    AUDIT_LOCK_TIMEOUT_SECONDS: float = 5.0
    BIAS_FLAG_THRESHOLD: float = 0.05

    # Price tolerance for the Agent 2 <-> Agent 3 consistency cross-check.
    PRICE_CONSISTENCY_TOLERANCE_USD: float = 0.5

    # ── LLM (Gemini via google-genai, same as Agents 1/3; mock for tests) ──
    LLM_PROVIDER: str = "gemini"  # production: "gemini"; "mock" is for tests only
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: Union[str, List[str]] = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # ── Derived / validated ────────────────────────────────────────────────
    def score_weights(self) -> Dict[str, float]:
        """The five Feature-1 breakdown weights, keyed by reported sub-score."""
        return {
            "colour_harmony": self.SB_W_COLOUR_HARMONY,
            "formality_match": self.SB_W_FORMALITY_MATCH,
            "occasion_fit": self.SB_W_OCCASION_FIT,
            "budget_fit": self.SB_W_BUDGET_FIT,
            "constraint_satisfaction": self.SB_W_CONSTRAINT_SAT,
        }

    @model_validator(mode="after")
    def validate_tuning(self) -> "Settings":
        """Fail loudly at startup on an unusable configuration."""
        weights = self.score_weights()
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                "Score-breakdown weights must sum to 1.0, got "
                f"{total:.6f}: " + ", ".join(f"{k}={v}" for k, v in weights.items())
                + ". Fix SB_W_* (env-overridable)."
            )
        bad = [k for k, v in weights.items() if not 0.0 <= v <= 1.0]
        if bad:
            raise ValueError(f"Score-breakdown weights must be within [0, 1]: {bad}")
        if not 0.0 <= self.LOW_CONFIDENCE_THRESHOLD <= 1.0:
            raise ValueError("LOW_CONFIDENCE_THRESHOLD must be within [0, 1]")
        if not 0.0 <= self.FORCED_LOW_CONFIDENCE_SCORE < self.LOW_CONFIDENCE_THRESHOLD:
            raise ValueError(
                "FORCED_LOW_CONFIDENCE_SCORE must be within [0, LOW_CONFIDENCE_THRESHOLD) "
                f"so a forced answer is always reported as Low confidence "
                f"(got {self.FORCED_LOW_CONFIDENCE_SCORE}, threshold {self.LOW_CONFIDENCE_THRESHOLD})"
            )
        if self.MAX_REOPTIMIZATION_ROUNDS < 0:
            raise ValueError("MAX_REOPTIMIZATION_ROUNDS must be >= 0")
        if self.MAX_EXCLUDED_PRODUCT_IDS <= 0:
            raise ValueError("MAX_EXCLUDED_PRODUCT_IDS must be > 0")
        if self.MAX_COUNTERFACTUALS < 0:
            raise ValueError("MAX_COUNTERFACTUALS must be >= 0")
        if self.COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD <= 0:
            raise ValueError("COUNTERFACTUAL_BUDGET_MAX_INCREASE_USD must be > 0")
        if self.COUNTERFACTUAL_MAX_SWAP_PROBES <= 0:
            raise ValueError("COUNTERFACTUAL_MAX_SWAP_PROBES must be > 0")
        if self.MAX_VERIFICATION_ISSUES <= 0:
            raise ValueError("MAX_VERIFICATION_ISSUES must be > 0")
        if self.VERIFICATION_ISSUE_TEXT_LIMIT <= 0:
            raise ValueError("VERIFICATION_ISSUE_TEXT_LIMIT must be > 0")
        if not 0.0 <= self.BIAS_FLAG_THRESHOLD <= 1.0:
            raise ValueError("BIAS_FLAG_THRESHOLD must be within [0, 1]")
        if not self.AUDIT_DB_PATH:
            self.AUDIT_DB_PATH = str(_REPO_ROOT / "agents" / "agent4_decision" / "data" / "audit.db")
        return self

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
