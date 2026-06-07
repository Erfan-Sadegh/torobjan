from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/torobjan.db"
    admin_password: str = "change-me"
    session_secret: str = "change-this-secret"
    upload_dir: str = "data/uploads"
    clarity_project_id: str = ""

    torob_base_url: str = "https://api.torob.com"
    torob_proxy_token: str = ""
    torob_iw1_header: str = ""
    torob_cookie: str = ""
    torob_csrf_token: str = ""
    torob_instance_id: int = 411147
    torob_timeout_seconds: float = Field(default=5, gt=0)
    torob_max_retries: int = Field(default=0, ge=0)
    torob_rate_limit_seconds: float = Field(default=0.25, ge=0)

    def validate_for_runtime(self) -> None:
        if self.app_env != "production":
            return
        if self.admin_password == "change-me":
            raise RuntimeError("ADMIN_PASSWORD must be set in production.")
        if self.session_secret == "change-this-secret":
            raise RuntimeError("SESSION_SECRET must be set in production.")
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("DATABASE_URL must point to Postgres in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
