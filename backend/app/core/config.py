from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_NAME: str = "DocSense"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "insecure-default-key-for-development-only-change-me"
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: str | list[str] = ["*"]

    # Supabase (Auth & Database)
    SUPABASE_URL: str = "http://localhost:54321"
    SUPABASE_ANON_KEY: str = "test-anon-key"
    SUPABASE_SERVICE_ROLE_KEY: str = "test-service-key"
    SUPABASE_JWT_SECRET: str = "test-jwt-secret-at-least-32-chars-long"
    SUPABASE_DB_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/postgres"

    # Cloudflare R2 (S3-compatible Object Storage)
    CLOUDFLARE_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "doc-action-vault-dev"
    R2_ENDPOINT_URL: str = ""
    R2_PRESIGNED_EXPIRATION_SECONDS: int = 3600  # 1 hour

    # AI Gateway (Portkey, Gemini, OpenAI)
    PORTKEY_API_KEY: str = ""
    PORTKEY_VIRTUAL_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""  # optional override (Azure/proxy/self-hosted gateways)
    DEFAULT_PRIMARY_MODEL: str = "gemini-1.5-pro"
    DEFAULT_FALLBACK_MODEL: str = "gpt-4o"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # Upstash Redis & Kafka
    UPSTASH_REDIS_URL: str = "redis://localhost:6379"
    UPSTASH_REDIS_TOKEN: str = ""
    UPSTASH_KAFKA_URL: str = ""
    UPSTASH_KAFKA_TOKEN: str = ""

    # Document Processing & Security Limits
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    MAX_PAGE_COUNT: int = 100
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    # Test-only auth bypass ("test-token-*"). MUST remain False outside CI.
    # See ISSUE-006: gated behind explicit opt-in, never implied by APP_ENV.
    ALLOW_TEST_TOKENS: bool = False

    @field_validator("ALLOW_TEST_TOKENS")
    @classmethod
    def forbid_test_tokens_in_production(cls, v: bool) -> bool:
        # Defense in depth: even a misconfigured prod env cannot enable it.
        if v:
            import os

            if os.getenv("APP_ENV", "").lower() == "production":
                raise ValueError("ALLOW_TEST_TOKENS must never be enabled in production")
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        return ["*"]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
