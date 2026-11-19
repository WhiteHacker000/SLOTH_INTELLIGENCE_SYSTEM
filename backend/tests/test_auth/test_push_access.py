from uuid import uuid4

import httpx
import pytest

from app.auth.push_access import PushAccess
from app.auth.sessions import SignedIn
from app.models import User


def octo() -> SignedIn:
    return SignedIn(User(id=uuid4(), github_id=7, login="octo"), "ghu_1")


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def push_access(responses: list[httpx.Response], clock: Clock) -> PushAccess:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer ghu_1"
        return responses.pop(0)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return PushAccess("https://api.github.com", ttl=300, clock=clock, http=http)


def test_push_access_is_asked_once_and_remembered_for_a_while() -> None:
    clock, user = Clock(), octo()
    access = push_access(
        [
            httpx.Response(200, json={"permissions": {"push": True}}),
            httpx.Response(200, json={"permissions": {"push": False}}),
        ],
        clock,
    )

    assert access.can_push(user, "a/b") is True
    assert access.can_push(user, "A/B") is True  # remembered, no second call
    clock.now = 301
    assert access.can_push(user, "a/b") is False


@pytest.mark.parametrize(
    "first", [httpx.Response(404), httpx.Response(200, json={"id": 1})]
)
def test_errors_and_missing_permissions_deny(first: httpx.Response) -> None:
    user = octo()
    access = push_access(
        [first, httpx.Response(200, json={"permissions": {"push": True}})], Clock()
    )

    assert access.can_push(user, "a/b") is False
    # A failed call is not remembered, so the next check asks GitHub again.
    # A real "no push" answer is remembered.
    expected = first.status_code != 200
    assert access.can_push(user, "a/b") is expected
