"""Application configuration using pydantic-settings."""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    WORKERS: int = Field(default=4, description="Number of worker processes")

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=8000, description="API port")
    API_V1_PREFIX: str = Field(default="/api/v1", description="API v1 prefix")
    RATE_LIMIT_PER_MINUTE: int = Field(default=1000, description="Rate limit per minute")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://aifw_user:aifw_password@localhost:5432/aifw",
        description="Database connection URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=20, description="Database pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, description="Database max overflow")

    # Redis Configuration
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )
    REDIS_VECTOR_INDEX: str = Field(
        default="prompt_embeddings",
        description="Redis vector index name",
    )
    REDIS_TTL_SECONDS: int = Field(default=3600, description="Redis TTL in seconds")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Redis max connections")

    # gRPC Configuration
    GRPC_PORT: int = Field(default=50051, description="gRPC server port")
    GRPC_MAX_WORKERS: int = Field(default=10, description="gRPC max workers")

    # Detection Engine Configuration
    REGEX_PATTERNS_FILE: Path = Field(
        default=Path("./config/patterns.yaml"),
        description="Regex patterns configuration file",
    )
    SEMANTIC_THRESHOLD: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Semantic similarity threshold",
    )
    POLICY_CONFIG_FILE: Path = Field(
        default=Path("./config/policies.yaml"),
        description="Policy configuration file",
    )

    # Embedding Configuration
    EMBEDDING_MODEL: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model name",
    )
    EMBEDDING_DIMENSION: int = Field(default=384, description="Embedding dimension")
    BATCH_SIZE: int = Field(default=32, description="Batch size for embeddings")
    USE_OPENAI_EMBEDDINGS: bool = Field(
        default=False,
        description="Use OpenAI embeddings instead of local model",
    )
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API key")

    # Security
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Secret key for signing",
    )
    API_KEY_HEADER: str = Field(default="X-API-Key", description="API key header name")

    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    METRICS_PORT: int = Field(default=8000, description="Metrics port (same as API)")

    # Cache Settings
    ENABLE_CACHE: bool = Field(default=True, description="Enable caching")
    CACHE_TTL: int = Field(default=3600, description="Cache TTL in seconds")

    # Audit Settings
    AUDIT_LOG_RETENTION_DAYS: int = Field(
        default=90,
        description="Audit log retention in days",
    )
    ENABLE_DETAILED_LOGGING: bool = Field(
        default=True,
        description="Enable detailed audit logging",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON string format
            if v.startswith("["):
                import json
                return json.loads(v)
            # Handle comma-separated format
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
