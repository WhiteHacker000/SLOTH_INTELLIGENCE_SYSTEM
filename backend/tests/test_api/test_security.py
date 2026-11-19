from collections.abc import Generator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.security import RateLimiter, get_question_limiter, require_admin
from app.auth.access import Caller, get_caller, limit_questions
from app.core.config import Settings, get_settings
from app.main import app


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_after_the_limit_and_frees_up_later() -> None:
    clock = Clock()
    limiter = RateLimiter(window=60, clock=clock)

    assert limiter.hit("a", 2) is None
    assert limiter.hit("a", 2) is None
    assert limiter.hit("a", 2) == 60
    assert limiter.hit("b", 2) is None

    clock.now = 60
    assert limiter.hit("a", 2) is None


def make_client(settings: Settings, limiter: RateLimiter | None = None) -> TestClient:
    test_app = FastAPI()

    @test_app.post("/write", dependencies=[Depends(require_admin)])
    def write() -> dict[str, bool]:
        return {"ok": True}

    @test_app.post("/ask")
    def ask(_: Annotated[None, Depends(limit_questions)]) -> dict[str, bool]:
        return {"ok": True}

    test_app.dependency_overrides[get_settings] = lambda: settings
    fresh = limiter or RateLimiter()
    test_app.dependency_overrides[get_question_limiter] = lambda: fresh
    test_app.dependency_overrides[get_caller] = lambda: Caller(None, admin=False)
    return TestClient(test_app)


def test_write_actions_are_open_when_no_key_is_set() -> None:
    client = make_client(Settings(admin_api_key=None))

    assert client.post("/write").status_code == 200


def test_write_actions_need_the_right_key() -> None:
    client = make_client(Settings(admin_api_key="secret"))

    assert client.post("/write").status_code == 401
    assert client.post("/write", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert client.post("/write", headers={"X-Admin-Key": "secret"}).status_code == 200


def test_too_many_questions_get_429_with_retry_after() -> None:
    client = make_client(Settings(questions_per_minute=1))

    assert client.post("/ask").status_code == 200
    response = client.post("/ask")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert "Try again in 60 seconds" in response.json()["detail"]


def test_zero_turns_the_question_limit_off() -> None:
    client = make_client(Settings(questions_per_minute=0))

    assert all(client.post("/ask").status_code == 200 for _ in range(20))


@pytest.fixture
def admin_client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_settings] = lambda: Settings(admin_api_key="secret")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_admin_status_reports_whether_the_key_works(admin_client: TestClient) -> None:
    assert admin_client.get("/api/v1/admin").json() == {
        "key_required": True,
        "key_valid": False,
    }
    response = admin_client.get("/api/v1/admin", headers={"X-Admin-Key": "secret"})
    assert response.json()["key_valid"] is True


def test_real_routes_reject_imports_without_the_key(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/repositories", json={"url": "a/b"})

    assert response.status_code == 401
