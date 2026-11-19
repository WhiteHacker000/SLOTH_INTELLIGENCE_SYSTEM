from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.auth.sessions import DEFAULT_LIFETIME

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"


class SignInFailed(RuntimeError):
    pass


@dataclass
class GitHubUser:
    github_id: int
    login: str
    avatar_url: str | None


@dataclass
class UserToken:
    value: str
    lifetime: timedelta


class GitHubSignIn:
    """The GitHub App's user sign-in: send people to GitHub, then trade the code."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        api_base_url: str = "https://api.github.com",
        http: httpx.Client | None = None,
    ) -> None:
        self.client_id, self.client_secret = client_id, client_secret
        self.redirect_uri, self.api_base_url = redirect_uri, api_base_url
        self.http = http or httpx.Client(timeout=10)

    def authorize_url(self, state: str) -> str:
        query = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    def exchange_code(self, code: str) -> UserToken:
        response = self._send(
            "POST",
            TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
        )
        # GitHub reports a bad or reused code with 200 and an "error" field.
        token = response.get("access_token")
        if not token:
            raise SignInFailed(response.get("error_description", "No token returned"))
        expires_in = response.get("expires_in")
        lifetime = timedelta(seconds=expires_in) if expires_in else DEFAULT_LIFETIME
        return UserToken(token, min(lifetime, DEFAULT_LIFETIME))

    def fetch_user(self, token: str) -> GitHubUser:
        user = self._send(
            "GET",
            f"{self.api_base_url}/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
            },
        )
        return GitHubUser(user["id"], user["login"], user.get("avatar_url"))

    def _send(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.http.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SignInFailed(f"GitHub sign-in failed: {error}") from error
