import pytest

from app.api.security import question_limiter
from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def reset_question_limit() -> None:
    """Each test starts with a fresh per-client question limit."""
    question_limiter.hits.clear()


@pytest.fixture(autouse=True)
def default_settings() -> None:
    """API tests use default settings, not the developer's .env."""
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
