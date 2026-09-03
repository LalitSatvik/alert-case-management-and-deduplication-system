import pytest

from app.config import Settings, get_settings

_URLS = {
    "database_url": "postgresql+asyncpg://app_user:pw@localhost/acms",
    "migration_database_url": "postgresql+asyncpg://acms_owner:pw@localhost/acms",
    "redis_url": "redis://localhost:6379/0",
}


def test_placeholder_jwt_secret_rejected_outside_local() -> None:
    with pytest.raises(ValueError, match="jwt_secret"):
        Settings(
            **_URLS,
            jwt_secret="change-me-in-real-deployments",
            environment="production",
        )


def test_short_jwt_secret_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="jwt_secret"):
        Settings(**_URLS, jwt_secret="x" * 31, environment="production")


def test_strong_jwt_secret_accepted_in_production() -> None:
    s = Settings(**_URLS, jwt_secret="y" * 40, environment="production")
    assert s.environment == "production"


def test_placeholder_jwt_secret_allowed_in_local() -> None:
    s = Settings(**_URLS, jwt_secret="change-me-in-real-deployments", environment="local")
    assert s.jwt_secret == "change-me-in-real-deployments"


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app_user:pw@localhost/acms")
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL", "postgresql+asyncpg://acms_owner:pw@localhost/acms"
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "b")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert isinstance(s, Settings)
        assert s.jwt_algorithm == "HS256"
        assert s.access_token_ttl_seconds == 900
        assert s.minio_bucket == "acms"
    finally:
        # Drop the Settings built from this test's monkeypatched env so later
        # tests (which do real JWT work) rebuild it from the process defaults
        # instead of inheriting the short 11-byte ``JWT_SECRET`` used here.
        get_settings.cache_clear()
