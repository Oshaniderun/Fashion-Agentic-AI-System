"""
Configuration for the FASHORA Outfit Decision service (Agent 4).

Same conventions as Agents 1-3:
- pydantic-settings reads the repo-root .env, so the canonical JWT_SECRET and
  AGENT_SERVICE_TOKEN are shared system-wide.
- Agent 4 is STATELESS: it adds no tables and never touches the shared
  database directly. It consumes validated upstream payloads over HTTP/JSON.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[4] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
