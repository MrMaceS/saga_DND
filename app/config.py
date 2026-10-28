from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки приложения (переменные окружения или .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gemini. Модели gemini-2.0-flash и gemini-1.5-pro выведены из эксплуатации (404),
    # поэтому по умолчанию актуальные стабильные.
    gemini_api_key: str = ""
    model_interpreter: str = "gemini-2.5-flash"
    model_narrator: str = "gemini-2.5-pro"
    ai_timeout_s: int = 20

    # Сервер
    host: str = "0.0.0.0"
    port: int = 8000
    dev: int = 0

    # БД
    database_url: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'data' / 'saga.db'}"

    # Кубики
    dice_seed: int | None = None

    @field_validator("dice_seed", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v in ("", None):
            return None
        return int(v)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip()) and self.gemini_api_key.strip() != "your_key_here"


settings = Settings()
