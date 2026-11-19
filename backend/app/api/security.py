import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
AdminKeyHeader = Annotated[str | None, Header()]


def admin_key_valid(settings: Settings, key: str | None) -> bool:
    """True if no admin key is configured, or if `key` matches it."""
    if settings.admin_api_key is None:
        return True
    expected = settings.admin_api_key.get_secret_value()
    return key is not None and secrets.compare_digest(key.encode(), expected.encode())


def require_admin(settings: SettingsDep, x_admin_key: AdminKeyHeader = None) -> None:
    if not admin_key_valid(settings, x_admin_key):
        raise HTTPException(401, "Admin key required")


class RateLimiter:
    """Allows `limit` requests per client in any `window` seconds, in memory."""

    def __init__(
        self, window: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.window, self.clock = window, clock
        self.hits: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def hit(self, client: str, limit: int) -> float | None:
        """Record a request. Returns seconds to wait if over the limit."""
        now = self.clock()
        with self.lock:
            hits = self.hits.setdefault(client, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + self.window - now
            hits.append(now)
            if len(self.hits) > 10_000:
                self._forget_idle(now)
            return None

    def _forget_idle(self, now: float) -> None:
        idle = [c for c, h in self.hits.items() if not h or h[-1] <= now - self.window]
        for client in idle:
            del self.hits[client]


question_limiter = RateLimiter()


def get_question_limiter() -> RateLimiter:
    return question_limiter
