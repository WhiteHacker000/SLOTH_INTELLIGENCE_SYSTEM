from typing import Any

from app.ingestion.estimate import TOKEN_NEEDED_MESSAGE, estimate_import
from app.ingestion.github_client import RateLimit


class FakeGitHub:
    def __init__(self, newest_number: int | None, remaining: int, token: bool) -> None:
        self.newest = [{"number": newest_number}] if newest_number else []
        self.rate_limit = RateLimit(limit=60, remaining=remaining)
        self.authenticated = token

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.newest

    def paginate(self, path: str, params: dict[str, Any] | None = None):
        return iter([])


def test_small_repository_needs_no_token() -> None:
    estimate = estimate_import(FakeGitHub(10, remaining=59, token=False), "a/b")

    assert estimate.items == 10
    assert estimate.api_calls < 59
    assert estimate.token_recommended is False
    assert estimate.message is None


def test_large_repository_recommends_token() -> None:
    estimate = estimate_import(FakeGitHub(3_700, remaining=59, token=False), "a/b")

    assert estimate.api_calls > 59
    assert estimate.token_recommended is True
    assert estimate.message == TOKEN_NEEDED_MESSAGE


def test_large_repository_with_token_gets_no_notice() -> None:
    estimate = estimate_import(FakeGitHub(3_700, remaining=4_999, token=True), "a/b")

    assert estimate.token_recommended is False


def test_empty_repository() -> None:
    estimate = estimate_import(FakeGitHub(None, remaining=59, token=False), "a/b")

    assert estimate.items == 0
    assert estimate.token_recommended is False
