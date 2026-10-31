from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://localhost/decision_intelligence"
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    ollama_base_url: str = "http://localhost:11434"
    gemma_model: str = "gemma3:4b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
