from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.auth import SESSION_COOKIE, get_github_sign_in
from app.auth.github import GitHubUser, SignInFailed, UserToken
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import app

SETTINGS = Settings(
    _env_file=None,
    github_app_client_id="Iv1.client",
    github_app_client_secret="secret",
    token_encryption_key=Fernet.generate_key().decode(),
)


class FakeGitHub:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def authorize_url(self, state: str) -> str:
        return f"https://github.com/login/oauth/authorize?state={state}"

    def exchange_code(self, code: str) -> UserToken:
        if self.fail:
            raise SignInFailed("bad code")
        return UserToken(f"ghu_{code}", timedelta(hours=8))

    def fetch_user(self, token: str) -> GitHubUser:
        return GitHubUser(7, "octo", "https://avatars.example/7")


@pytest.fixture
def client(db_session: Session):
    db_session.commit = db_session.flush  # keep the test's rollback working
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_github_sign_in] = FakeGitHub
    try:
        yield TestClient(app, follow_redirects=False)
    finally:
        app.dependency_overrides.clear()


def sign_in(client: TestClient):
    state = parse_qs(
        urlparse(client.get("/api/v1/auth/login").headers["location"]).query
    )
    return client.get(
        "/api/v1/auth/callback", params={"code": "abc", "state": state["state"][0]}
    )


def test_signing_in_sets_a_session_and_returns_to_the_app(client: TestClient) -> None:
    response = sign_in(client)

    assert response.status_code == 302
    assert response.headers["location"] == SETTINGS.app_url
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = client.get("/api/v1/auth/me").json()
    assert me == {
        "sign_in_enabled": True,
        "user": {"login": "octo", "avatar_url": "https://avatars.example/7"},
    }


def test_a_state_not_issued_to_this_browser_is_refused(client: TestClient) -> None:
    client.get("/api/v1/auth/login")

    response = client.get(
        "/api/v1/auth/callback", params={"code": "abc", "state": "forged"}
    )

    assert response.status_code == 400
    assert client.get("/api/v1/auth/me").json()["user"] is None


def test_github_failures_do_not_sign_in(client: TestClient) -> None:
    app.dependency_overrides[get_github_sign_in] = lambda: FakeGitHub(fail=True)

    assert sign_in(client).status_code == 502
    assert SESSION_COOKIE not in client.cookies


def test_signing_out_ends_the_session(client: TestClient) -> None:
    sign_in(client)
    session_cookie = client.cookies[SESSION_COOKIE]

    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set(SESSION_COOKIE, session_cookie)  # even if the browser kept it
    assert client.get("/api/v1/auth/me").json()["user"] is None


def test_sign_in_is_off_without_the_app_settings(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    del app.dependency_overrides[get_github_sign_in]

    assert client.get("/api/v1/auth/login").status_code == 503
    assert client.get("/api/v1/auth/me").json() == {
        "sign_in_enabled": False,
        "user": None,
    }
