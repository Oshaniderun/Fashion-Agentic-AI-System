from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, model_validator
from functools import lru_cache
from typing import Optional, List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "FASHORA Agent 2 - Fashion Retrieval"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT", "ENV"))
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "agent2_retrieval"
    
    # Chroma
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"
    
    # Canonical JWT / Security Configuration
    JWT_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY"),
        description="Secret key used for signing and verifying JWT tokens."
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "JWT_EXPIRY_MINUTES")
    )
    
    # Inter-agent Service Token
    AGENT_SERVICE_TOKEN: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AGENT_SERVICE_TOKEN", "SERVICE_TOKEN"),
        description="Shared secret token used for inter-agent authentication."
    )

    # CORS Allowed Origins
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
        description="Comma-separated list of allowed CORS origins."
    )

    DATABASE_URL: Optional[str] = None
    BM25_INDEX_PATH: str = "./data/processed/bm25_index.pkl"
    DATASET_PATH: str = "./data/processed/products_cleaned.json"
    TESTING: bool = False

    @property
    def SECRET_KEY(self) -> str:
        """Backward compatibility accessor for JWT secret."""
        return self.JWT_SECRET or ""

    @property
    def SERVICE_TOKEN(self) -> str:
        """Backward compatibility accessor for inter-agent service token."""
        return self.AGENT_SERVICE_TOKEN or ""

    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed list of allowed CORS origins."""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @model_validator(mode="after")
    def validate_and_fallback_credentials(self):
        is_production = self.ENVIRONMENT.lower() in ("production", "prod")

        if is_production:
            missing = []
            if not self.JWT_SECRET:
                missing.append("JWT_SECRET")
            if not self.AGENT_SERVICE_TOKEN:
                missing.append("AGENT_SERVICE_TOKEN")
            if missing:
                raise ValueError(
                    f"Production configuration error: Missing required secret(s): {', '.join(missing)}. "
                    "Must be provided via environment variables."
                )
        else:
            # Isolated development/testing safe fallbacks
            if not self.JWT_SECRET:
                self.JWT_SECRET = "dev_only_jwt_secret_for_local_testing"
            if not self.AGENT_SERVICE_TOKEN:
                self.AGENT_SERVICE_TOKEN = "dev_only_service_token_for_local_testing"

        return self

@lru_cache()
def get_settings():
    return Settings()

