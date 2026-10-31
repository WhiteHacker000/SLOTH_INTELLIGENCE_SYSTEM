from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.repositories import RATE_LIMIT_MESSAGE, get_github_factory
from app.db.session import get_session
from app.ingestion.estimate import TOKEN_NEEDED_MESSAGE
from app.ingestion.github_client import (
    RateLimit,
    RateLimitExceeded,
    RepositoryNotFound,
)
from app.main import app

META = {"id": 1, "full_name": "a/b", "html_url": "https://github.com/a/b"}


class FakeGitHub:
    def __init__(self, token: str | None, newest: int, missing: bool | str) -> None:
        self.authenticated = bool(token)
        self.rate_limit = RateLimit(remaining=4999 if token else 59)
        self.newest, self.missing = newest, missing

    def __enter__(self) -> "FakeGitHub":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self.missing == "rate":
            raise RateLimitExceeded(reset_at=None)
        if self.missing:
            raise RepositoryNotFound("not found")
        return [{"number": self.newest}] if path.endswith("/issues") else META


@pytest.fixture
def api(db_session: Session) -> Generator[dict[str, Any], None, None]:
    state: dict[str, Any] = {"newest": 5, "missing": False, "tokens": []}

    def factory(token: str | None) -> FakeGitHub:
        state["tokens"].append(token)
        return FakeGitHub(token, state["newest"], state["missing"])

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_github_factory] = lambda: factory
    state["client"] = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def test_register_small_repository(api: dict[str, Any]) -> None:
    response = api["client"].post(
        "/api/v1/repositories", json={"url": "https://github.com/a/b.git"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["repository"]["full_name"] == "a/b"
    assert body["estimate"]["token_recommended"] is False


def test_large_repository_without_token_gets_notice(api: dict[str, Any]) -> None:
    api["newest"] = 5_000

    body = api["client"].post("/api/v1/repositories", json={"url": "a/b"}).json()

    assert body["estimate"]["token_recommended"] is True
    assert body["estimate"]["message"] == TOKEN_NEEDED_MESSAGE


def test_registering_twice_returns_same_repository(api: dict[str, Any]) -> None:
    first = api["client"].post("/api/v1/repositories", json={"url": "a/b"}).json()
    second = api["client"].post("/api/v1/repositories", json={"url": "a/b"}).json()

    assert first["repository"]["id"] == second["repository"]["id"]
    listed = api["client"].get("/api/v1/repositories").json()
    assert [repo["full_name"] for repo in listed] == ["a/b"]


@pytest.mark.parametrize("url", ["not a url", "https://gitlab.com/a/b", "a"])
def test_invalid_url_is_rejected(api: dict[str, Any], url: str) -> None:
    response = api["client"].post("/api/v1/repositories", json={"url": url})

    assert response.status_code == 422


def test_missing_github_repository_returns_404(api: dict[str, Any]) -> None:
    api["missing"] = True

    response = api["client"].post("/api/v1/repositories", json={"url": "a/b"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Repository not found on GitHub"


def test_rate_limit_asks_for_token(api: dict[str, Any]) -> None:
    api["missing"] = "rate"

    response = api["client"].post("/api/v1/repositories", json={"url": "a/b"})

    assert response.status_code == 429
    assert response.json()["detail"] == RATE_LIMIT_MESSAGE
