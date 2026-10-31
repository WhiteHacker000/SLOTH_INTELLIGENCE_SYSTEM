from collections.abc import Callable

import httpx
import pytest

from app.ingestion.github_client import (
    GitHubClient,
    GitHubError,
    GitHubUnavailable,
    RateLimitExceeded,
    RepositoryNotFound,
)

BASE_URL = "https://api.github.com"
Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, token: str | None = None) -> GitHubClient:
    return GitHubClient(
        BASE_URL,
        token,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def rate_headers(remaining: int) -> dict[str, str]:
    return {
        "x-ratelimit-limit": "60",
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": "1767225600",
    }


def test_sends_token_only_when_given() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={})

    make_client(handler, token="secret").get_json("/repos/a/b")
    make_client(handler).get_json("/repos/a/b")

    assert seen == ["Bearer secret", None]


def test_paginate_follows_link_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 3}])
        assert request.url.params["per_page"] == "100"
        next_link = f'<{BASE_URL}/repos/a/b/issues?per_page=100&page=2>; rel="next"'
        return httpx.Response(
            200, json=[{"id": 1}, {"id": 2}], headers={"link": next_link}
        )

    items = list(make_client(handler).paginate("/repos/a/b/issues"))

    assert [item["id"] for item in items] == [1, 2, 3]


def test_tracks_remaining_rate_limit() -> None:
    client = make_client(
        lambda _: httpx.Response(200, json={}, headers=rate_headers(42))
    )

    client.get_json("/repos/a/b")

    assert client.rate_limit.limit == 60
    assert client.rate_limit.remaining == 42
    assert client.rate_limit.reset_at is not None


def test_raises_rate_limit_when_quota_is_used_up() -> None:
    client = make_client(lambda _: httpx.Response(403, headers=rate_headers(0)))

    with pytest.raises(RateLimitExceeded) as error:
        client.get_json("/repos/a/b")

    assert error.value.reset_at is not None


def test_raises_rate_limit_on_secondary_limit() -> None:
    client = make_client(lambda _: httpx.Response(429, headers={"retry-after": "30"}))

    with pytest.raises(RateLimitExceeded):
        client.get_json("/repos/a/b")


def test_missing_repository_raises_not_found() -> None:
    client = make_client(lambda _: httpx.Response(404, json={"message": "Not Found"}))

    with pytest.raises(RepositoryNotFound):
        client.get_json("/repos/a/missing")


def test_retries_server_errors_then_succeeds() -> None:
    responses = iter([httpx.Response(502), httpx.Response(200, json={"ok": True})])
    client = make_client(lambda _: next(responses))

    assert client.get_json("/repos/a/b") == {"ok": True}


def test_gives_up_after_repeated_network_failures() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(GitHubUnavailable):
        make_client(handler).get_json("/repos/a/b")

    assert attempts == 4


def test_invalid_json_raises_github_error() -> None:
    client = make_client(lambda _: httpx.Response(200, content=b"<html>"))

    with pytest.raises(GitHubError):
        client.get_json("/repos/a/b")


def test_client_repr_does_not_expose_token() -> None:
    client = make_client(lambda _: httpx.Response(200), token="secret")

    assert "secret" not in repr(client)
    assert "secret" not in repr(vars(client))
