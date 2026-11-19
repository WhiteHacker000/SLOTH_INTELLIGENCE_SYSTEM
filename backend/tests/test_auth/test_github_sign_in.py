from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.github import GitHubSignIn, SignInFailed


def github(handler) -> GitHubSignIn:
    return GitHubSignIn(
        "Iv1.client",
        "secret",
        "http://localhost:8000/api/v1/auth/callback",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_authorize_url_carries_client_callback_and_state() -> None:
    url = urlparse(github(lambda r: httpx.Response(200)).authorize_url("xyz"))

    assert url.netloc == "github.com"
    assert parse_qs(url.query) == {
        "client_id": ["Iv1.client"],
        "redirect_uri": ["http://localhost:8000/api/v1/auth/callback"],
        "state": ["xyz"],
    }


def test_exchange_code_returns_the_token_and_its_lifetime() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"code=abc" in request.content
        return httpx.Response(200, json={"access_token": "ghu_1", "expires_in": 3600})

    token = github(handler).exchange_code("abc")

    assert token.value == "ghu_1"
    assert token.lifetime == timedelta(hours=1)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"error": "bad_verification_code"}),
        httpx.Response(500),
        httpx.Response(200, text="not json"),
    ],
)
def test_failed_exchanges_raise(response: httpx.Response) -> None:
    with pytest.raises(SignInFailed):
        github(lambda r: response).exchange_code("abc")


def test_fetch_user_sends_the_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer ghu_1"
        return httpx.Response(200, json={"id": 7, "login": "octo"})

    user = github(handler).fetch_user("ghu_1")

    assert (user.github_id, user.login, user.avatar_url) == (7, "octo", None)
