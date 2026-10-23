from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # BE-2: unknown env vars (typos like REDIS_URL, stale keys) must fail
        # loudly at startup instead of being silently ignored.
        extra="forbid",
    )

    # Core Application
    APP_NAME: str = "DocSense"
    APP_ENV: str = "development"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
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

    # AI Gateway (Portkey, Gemini, OpenAI)
    PORTKEY_API_KEY: str = ""
    PORTKEY_VIRTUAL_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""  # optional override (Azure/proxy/self-hosted gateways)
    DEFAULT_PRIMARY_MODEL: str = "gemini-1.5-pro"
    DEFAULT_FALLBACK_MODEL: str = "gpt-4o"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Upstash Redis & Kafka
    UPSTASH_REDIS_URL: str = "redis://localhost:6379"
    UPSTASH_REDIS_TOKEN: str = ""
    UPSTASH_KAFKA_URL: str = ""
    UPSTASH_KAFKA_TOKEN: str = ""

    # Document Processing & Security Limits
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=25 * 1024 * 1024, gt=0, le=100 * 1024 * 1024
    )  # 25 MB
    MAX_PAGE_COUNT: int = Field(default=100, ge=1, le=1000)
    R2_PRESIGNED_EXPIRATION_SECONDS: int = Field(default=3600, ge=60, le=86400)  # 1 min .. 24 h
    EMBEDDING_DIMENSION: int = Field(default=1536, ge=1, le=4096)
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

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}, got {v!r}")
        return v

    @field_validator("ALLOWED_MIME_TYPES")
    @classmethod
    def validate_mime_types(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("ALLOWED_MIME_TYPES must not be empty")
        for mt in v:
            if "/" not in mt:
                raise ValueError(f"Invalid MIME type (expected 'type/subtype'): {mt!r}")
        return v

    @model_validator(mode="after")
    def enforce_production_hardening(self) -> "Settings":
        """BE-2 + BE-3: fail-fast startup checks for production deployments.

        A misconfigured production deploy should crash at boot with a clear
        message rather than run insecurely (weak secrets, wildcard CORS,
        dev/test credentials).
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        if self.SECRET_KEY.startswith("insecure-default-key"):
            problems.append("SECRET_KEY is still the insecure development default")
        if len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be at least 32 characters")
        if len(self.SUPABASE_JWT_SECRET) < 32:
            problems.append("SUPABASE_JWT_SECRET must be at least 32 characters")
        if self.SUPABASE_SERVICE_ROLE_KEY in ("", "test-service-key"):
            problems.append(
                "SUPABASE_SERVICE_ROLE_KEY must be configured (erasure & admin ops depend on it)"
            )
        if not self.SUPABASE_URL.startswith("https://"):
            problems.append("SUPABASE_URL must use https:// in production")
        if not self.UPSTASH_REDIS_URL.startswith(("redis://", "rediss://")):
            problems.append("UPSTASH_REDIS_URL must be a redis:// or rediss:// URL")
        if not any((self.OPENAI_API_KEY, self.GEMINI_API_KEY, self.PORTKEY_API_KEY)):
            problems.append(
                "At least one AI gateway key (OPENAI/GEMINI/PORTKEY) must be configured"
            )
        if "*" in self.ALLOWED_ORIGINS:
            problems.append(
                "ALLOWED_ORIGINS must be an explicit comma-separated list in "
                "production (wildcard '*' with credentials is unsafe and browser-rejected)"
            )

        if problems:
            raise ValueError("Invalid production configuration:\n- " + "\n- ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
