from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_JWT_SECRET = "change-me-in-real-deployments"
_MIN_JWT_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    migration_database_url: str
    redis_url: str
    # Object storage is a Phase 2 concern (case attachments / import reports).
    # These stay declared so a future .env can wire Garage or an S3 API without a
    # code change, but they are unset in the MVP and must never block startup.
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "acms"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 86400
    idempotency_ttl_seconds: int = 604800
    grouping_config_path: str = "config/grouping.yaml"
    environment: str = "local"

    # NFR-SEC-08: Valkey-backed fixed-window rate limits. Generous ceilings --
    # they exist to blunt credential-stuffing and ingest floods, not to shape
    # normal traffic.
    auth_rate_limit_per_minute: int = 10
    ingest_rate_limit_per_minute: int = 120
    # NFR-SEC-07: hard cap on a single :batch submission.
    batch_max_items: int = 5000

    @model_validator(mode="after")
    def _reject_placeholder_jwt_secret(self) -> Settings:
        """Outside ``environment == "local"`` the JWT secret must be real.

        Runs ``mode="after"`` so it sees the resolved ``environment`` regardless
        of field order. ``local`` stays permissive so the dev/test flow needs no
        secret management.
        """
        if self.environment != "local" and (
            self.jwt_secret == _PLACEHOLDER_JWT_SECRET or len(self.jwt_secret) < _MIN_JWT_SECRET_LEN
        ):
            raise ValueError(
                "jwt_secret must be a unique value of at least "
                f"{_MIN_JWT_SECRET_LEN} characters when environment is not 'local'"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
