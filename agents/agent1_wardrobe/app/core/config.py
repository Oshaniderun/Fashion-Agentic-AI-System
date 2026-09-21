"""
Configuration settings for Agent 1 (Style & Wardrobe Intelligence Agent).
"""

from typing import List, Union
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str = "FASHORA Agent 1 — Style & Wardrobe Intelligence"
    APP_ENV: str = "development"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Database
    DATABASE_URL: str = "sqlite:///./fashora_agent1.db"

    # Security & Authentication
    JWT_SECRET: str = "fashora_agent1_dev_jwt_secret_key_2026_secure"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 120
    AGENT_SERVICE_TOKEN: str = "fashora_shared_service_token_2026"

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]

    # AI & Model Providers
    LLM_PROVIDER: str = "mock"  # "mock", "gemini", "openai", "anthropic"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    VISION_MODEL_BACKEND: str = "auto"  # "auto", "local", "clip"

    # Demo seed (W001-W005 + demo@fashora.ai). Keep false for production-like runs.
    SEED_DEMO_DATA: bool = False

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure uploads directory exists
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
