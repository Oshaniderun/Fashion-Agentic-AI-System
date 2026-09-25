"""
Configuration for the FASHORA Budget & Purchase Planning service (Agent 3).

Follows the same conventions as Agents 1 and 2:
- pydantic-settings reading the repo-root .env, so the canonical JWT_SECRET,
  AGENT_SERVICE_TOKEN, DATABASE_URL and LLM_* values are shared system-wide.
- DATABASE_URL is propagated into os.environ before any shared model import,
  so shared/models/database.py binds to the SAME PostgreSQL database as the
  rest of the system (Agent 3 only adds its own budget_* tables).
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "FASHORA Budget & Purchase Planning Service"
    VERSION: str = "2.0.0"
    # SERVICE_HOST/SERVICE_PORT avoid the generic HOST/PORT keys in the root
    # .env, which belong to Agent 1 (8001).
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8003
    ENVIRONMENT: str = "development"

    # ── Database (shared with Agents 1 & 2 via root .env) ──────────────────
    DATABASE_URL: str = "sqlite:///./fashora.db"

    # ── Security / Authentication (root .env supplies the real values) ─────
    JWT_SECRET: str = "fashora_agent1_dev_jwt_secret_key_2026_secure"
    JWT_ALGORITHM: str = "HS256"
    AGENT_SERVICE_TOKEN: str = "fashora_shared_service_token_2026"

    # ── Currency / commercial policy (USD everywhere in this repo) ─────────
    CURRENCY: str = "USD"
    FREE_TIER_MONTHLY_LIMIT: int = 3
    PREMIUM_MONTHLY_PRICE_USD: float = 3.99
    AFFILIATE_COMMISSION_RATE: float = 0.05
    AFFILIATE_BASE_URL: str = "http://localhost:8003"

    # ── Optimizer tuning ────────────────────────────────────────────────────
    DEFAULT_MAX_COMBINATIONS: int = 2000

    # ── Inter-agent links (feedback loop: this service -> Agent 2) ─────────
    AGENT2_BASE_URL: str = "http://127.0.0.1:8002"
    AGENT2_SEARCH_TIMEOUT_SECONDS: float = 30.0
    FEEDBACK_LOOP_MAX_ROUNDS: int = 2

    # ── LLM (Gemini via google-genai, same as Agent 1; mock for tests) ─────
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

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[4] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# ── Handshake with the shared DB layer: shared/models/database.py reads
# DATABASE_URL from os.environ at import time. Must run BEFORE that import.
os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
