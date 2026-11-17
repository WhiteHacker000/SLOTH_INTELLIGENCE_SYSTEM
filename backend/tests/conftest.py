import pytest

from app.api.security import question_limiter


@pytest.fixture(autouse=True)
def reset_question_limit() -> None:
    """Each test starts with a fresh per-client question limit."""
    question_limiter.hits.clear()
