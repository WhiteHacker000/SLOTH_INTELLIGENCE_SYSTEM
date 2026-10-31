import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
RETRY_STATUSES = {500, 502, 503, 504}


class GitHubError(Exception):
    """Base error for GitHub API failures."""


class RepositoryNotFound(GitHubError):
    pass


class GitHubUnavailable(GitHubError):
    pass


class RateLimitExceeded(GitHubError):
    def __init__(self, reset_at: datetime | None) -> None:
        super().__init__("GitHub rate limit reached")
        self.reset_at = reset_at


@dataclass
class RateLimit:
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None


class GitHubClient:
    """Read-only GitHub REST client.

    The token is kept in memory for this client only and never logged.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.authenticated = bool(token)
        self.rate_limit = RateLimit()
        self._max_retries = max_retries
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url, headers=headers, timeout=timeout, transport=transport
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._parse(self._request(path, params))

    def paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        """Yield every item across pages, following the Link header."""
        url: str | None = path
        page_params: dict[str, Any] | None = {**(params or {}), "per_page": PAGE_SIZE}
        while url:
            response = self._request(url, page_params)
            items = self._parse(response)
            if not isinstance(items, list):
                raise GitHubError(f"Expected a list from {path}")
            yield from items
            url = response.links.get("next", {}).get("url")
            page_params = None  # the next URL already carries the query

    def _request(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.get(url, params=params)
            except httpx.TransportError as error:
                if attempt == self._max_retries:
                    raise GitHubUnavailable("Could not reach GitHub") from error
                self._backoff(attempt)
                continue

            self._update_rate_limit(response)
            if response.status_code in RETRY_STATUSES and attempt < self._max_retries:
                self._backoff(attempt)
                continue
            self._raise_for_status(response)
            return response
        raise GitHubUnavailable("Could not reach GitHub")

    def _backoff(self, attempt: int) -> None:
        delay = 2**attempt
        logger.warning("GitHub request failed, retrying in %ss", delay)
        self._sleep(delay)

    def _update_rate_limit(self, response: httpx.Response) -> None:
        headers = response.headers
        if "x-ratelimit-remaining" not in headers:
            return
        self.rate_limit = RateLimit(
            limit=int(headers.get("x-ratelimit-limit", 0)),
            remaining=int(headers["x-ratelimit-remaining"]),
            reset_at=datetime.fromtimestamp(
                int(headers.get("x-ratelimit-reset", 0)), UTC
            ),
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == 404:
            raise RepositoryNotFound("Repository or resource not found")
        if status in (403, 429) and (
            self.rate_limit.remaining == 0 or "retry-after" in response.headers
        ):
            raise RateLimitExceeded(self.rate_limit.reset_at)
        if status >= 500:
            raise GitHubUnavailable(f"GitHub returned {status}")
        raise GitHubError(f"GitHub returned {status}")

    @staticmethod
    def _parse(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as error:
            raise GitHubError("GitHub returned invalid JSON") from error


def create_github_client(token: str | None = None) -> GitHubClient:
    """Use the token from the request, else GITHUB_TOKEN, else go anonymous."""
    settings = get_settings()
    return GitHubClient(settings.github_api_base_url, token or settings.github_token)
