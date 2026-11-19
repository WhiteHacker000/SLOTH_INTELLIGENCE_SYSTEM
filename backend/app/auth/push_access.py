import threading
import time
from collections.abc import Callable
from uuid import UUID

import httpx

from app.api.security import SettingsDep
from app.auth.sessions import SignedIn


class PushAccess:
    """Asks GitHub whether a user can push to a repository.

    Answers are kept for a few minutes, so clicking a button twice does not cost
    two GitHub calls, while losing access still takes effect soon.
    """

    def __init__(
        self,
        api_base_url: str,
        ttl: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        http: httpx.Client | None = None,
    ) -> None:
        self.api_base_url, self.ttl, self.clock = api_base_url, ttl, clock
        self.http = http or httpx.Client(timeout=10)
        self.answers: dict[tuple[UUID, str], tuple[bool, float]] = {}
        self.lock = threading.Lock()

    def can_push(self, user: SignedIn, full_name: str) -> bool:
        key = (user.user.id, full_name.lower())
        with self.lock:
            cached = self.answers.get(key)
        if cached and cached[1] > self.clock():
            return cached[0]
        try:
            response = self.http.get(
                f"{self.api_base_url}/repos/{full_name}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {user.github_token}",
                },
            )
            response.raise_for_status()
            allowed = bool(response.json().get("permissions", {}).get("push"))
        except (httpx.HTTPError, ValueError):
            return False  # not remembered, so the next click asks again
        with self.lock:
            self.answers[key] = (allowed, self.clock() + self.ttl)
        return allowed


_push_access: PushAccess | None = None


def get_push_access(settings: SettingsDep) -> PushAccess:
    global _push_access
    if _push_access is None:
        _push_access = PushAccess(settings.github_api_base_url)
    return _push_access
