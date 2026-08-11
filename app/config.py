"""Конфигурация приложения через переменные окружения."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Общие
    app_name: str = "KMGE Edu — СДО"
    environment: str = "development"

    # База данных. По умолчанию — Postgres (docker-compose).
    # Для локального smoke-теста можно подставить sqlite+aiosqlite.
    database_url: str = "postgresql+asyncpg://edu:edu@localhost:5432/edu"

    # Безопасность / JWT
    secret_key: str = "CHANGE_ME_super_secret_key_for_dev_only"
    access_token_expire_minutes: int = 60 * 24  # 24 часа
    algorithm: str = "HS256"

    # CORS (Flutter web dev-сервер)
    cors_origins: str = "*"

    # AI-ассистент (Claude). Если ключ пуст — AI-функции отдают 503.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Первичный администратор (создаётся при старте, если БД пуста)
    first_admin_email: str = "admin@kmge.kz"
    first_admin_password: str = "admin12345"
    first_admin_name: str = "Администратор"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
