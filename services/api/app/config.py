"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "EHA"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    allowed_origins: str = "http://localhost:19006,http://localhost:8081"

    # Database
    database_url: str = "postgresql+asyncpg://eha:eha_dev@localhost:5432/eha"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_private_key: SecretStr = SecretStr("dev-private-key-change-in-production")
    jwt_public_key: SecretStr = SecretStr("dev-public-key-change-in-production")
    jwt_algorithm: str = "HS256"  # Use RS256 in production
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_pubsub_topic: str = ""
    google_pubsub_verification_token: SecretStr = SecretStr("")

    # Encryption (libsodium key, base64 encoded)
    encryption_key: SecretStr = SecretStr("")

    # AI Provider
    ai_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Push notifications
    fcm_credentials_json: str = ""  # Path to Firebase service account JSON
    apns_key_path: str = ""
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_bundle_id: str = "com.eha.app"

    # Rate limiting
    rate_limit_per_minute: int = 100

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Gmail polling fallback interval (seconds)
    gmail_poll_interval: int = 60

    @field_validator("allowed_origins")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
