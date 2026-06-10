"""
app/core/config.py
──────────────────
Central configuration module. All environment variables are read here.
Every other module imports `settings` from this file — never reads os.environ directly.

Usage:
    from app.core.config import settings
    print(settings.DATABASE_URL)
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables + .env file.
    Pydantic validates all values on startup — the app fails fast if config is wrong.
    """

    model_config = SettingsConfigDict(
        env_file=".env",                # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,           # DATABASE_URL == database_url
        extra="ignore",                 # Silently ignore unknown env vars
        validate_default=True,          # Validate even fields with defaults
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "India Railways Delay Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # ── API ────────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ───────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Accepts "http://localhost:3000,http://localhost:5173" as a comma-separated string
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── MLflow ─────────────────────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "india_railways_delay_prediction"

    # ── ML Models ──────────────────────────────────────────────────────────────
    MODEL_DIR: str = "ml/saved_models"
    ACTIVE_MODEL_NAME: str = "xgboost_delay_predictor"

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # ── Pagination ─────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200

    # ── Validators ─────────────────────────────────────────────────────────────

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(
                f"ENVIRONMENT='{v}' is invalid. Must be one of: {allowed}"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if v == "REPLACE_THIS_with_python_secrets_token_hex_32":
            raise ValueError(
                "SECRET_KEY is still the placeholder value. "
                "Generate a real key: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql://'. "
                "Example: postgresql://user:pass@localhost:5432/dbname"
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return v.upper()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """
        Accepts either:
        - A list already: ["http://localhost:3000"]
        - A comma-separated string from .env: "http://localhost:3000,http://localhost:5173"
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Extra validation rules that only apply in production."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if self.DB_ECHO:
                raise ValueError("DB_ECHO must be false in production (SQL logs are a security risk)")
            if "localhost" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL should not point to localhost in production")
        return self

    # ── Computed Properties ────────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == "staging"

    @property
    def access_token_expire_seconds(self) -> int:
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    The @lru_cache means this reads .env exactly once — not on every import.

    Use this function as a FastAPI dependency for easy testing:
        @router.get("/")
        def route(settings: Settings = Depends(get_settings)):
            ...

    Override in tests:
        app.dependency_overrides[get_settings] = lambda: Settings(SECRET_KEY="test-key-32chars")
    """
    return Settings()


# Module-level singleton for non-FastAPI code (services, repositories, CLI scripts)
# Usage: from app.core.config import settings
settings: Settings = get_settings()