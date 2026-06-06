import pytest

from app.settings import Settings


def test_production_rejects_default_admin_password() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg://user:pass@localhost/db",
        admin_password="change-me",
        session_secret="long-secret",
    )

    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        settings.validate_for_runtime()


def test_production_rejects_sqlite_database() -> None:
    settings = Settings(
        app_env="production",
        database_url="sqlite:///./data/torobjan.db",
        admin_password="strong-password",
        session_secret="long-secret",
    )

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        settings.validate_for_runtime()
