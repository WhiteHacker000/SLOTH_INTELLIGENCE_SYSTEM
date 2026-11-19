from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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
    # Production only: folder of the built frontend, served from "/".
    frontend_dist: Path | None = None
    # Load both models when the server starts, so the first answer is not slow.
    warm_up_models: bool = False
    # When set, import, sync and extraction need this key in X-Admin-Key.
    admin_api_key: SecretStr | None = None
    # Run queued syncs and extractions in this process.
    run_job_worker: bool = True
    # Per client IP, for search and ask. 0 turns the limit off.
    questions_per_minute: int = 10
    # Fernet key that encrypts users' GitHub tokens. Sign-in is off without it.
    token_encryption_key: SecretStr | None = None
    # The SilS GitHub App, used to sign people in.
    github_app_client_id: str | None = None
    github_app_client_secret: SecretStr | None = None
    # Where this API is reachable from browsers; GitHub returns users here.
    public_url: str = "http://localhost:8000"
    # Where people land after signing in. The same as public_url in production.
    app_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
