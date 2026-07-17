from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://stepik_panel:stepik_panel@localhost:5432/stepik_panel"
    redis_url: str = "redis://localhost:6379/0"

    stepik_client_id: str = ""
    stepik_client_secret: str = ""
    stepik_redirect_uri: str = "http://localhost:3000/api/auth/callback"
    stepik_user_id: int = 0

    stepik_finance_client_id: str = ""
    stepik_finance_client_secret: str = ""

    encryption_key: str = ""
    secret_key: str = "dev-secret-key"

    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
