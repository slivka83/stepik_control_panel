import logging
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://stepik_panel:stepik_panel@localhost:5433/stepik_panel"
    redis_url: str = "redis://:stepik_redis@localhost:6380/0"

    stepik_client_id: str = ""
    stepik_client_secret: str = ""
    stepik_user_id: int = 0

    stepik_finance_client_id: str = ""
    stepik_finance_client_secret: str = ""

    encryption_key: str = ""
    secret_key: str = "dev-secret-key"

    app_env: str = "development"
    frontend_port: int = 3000
    session_ttl_hours: int = 24
    allowed_origins: str = ""

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.app_env == "production":
            if not self.secret_key or self.secret_key == "dev-secret-key":
                raise RuntimeError(
                    "SECRET_KEY must be set in production (not 'dev-secret-key'). Generate with: openssl rand -hex 32"
                )
            if len(self.secret_key) < 32:
                raise RuntimeError("SECRET_KEY must be at least 32 characters in production")
            if not self.encryption_key:
                raise RuntimeError("ENCRYPTION_KEY must be set in production")
        else:
            if self.secret_key == "dev-secret-key":
                logger.warning("Using default SECRET_KEY='dev-secret-key' — do NOT use in production!")
        return self

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.frontend_port}"

    @property
    def stepik_redirect_uri(self) -> str:
        return f"http://localhost:{self.frontend_port}/api/auth/callback"

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
