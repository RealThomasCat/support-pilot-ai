from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "SupportPilot AI"
    environment: str = "local"

    database_url: str = (
        "postgresql+psycopg://supportpilot:supportpilot@localhost:5433/supportpilot"
    )

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_max_tool_rounds: int = Field(
    default=5,
    ge=1,
    le=10,
)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
