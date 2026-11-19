from typing import Annotated
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.security import RateLimiter, get_question_limiter
from app.auth.access import (
    Caller,
    get_caller,
    limit_questions,
    require_member,
)
from app.auth.sessions import SignedIn
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User

SIGN_IN = {
    "github_app_client_id": "Iv1.client",
    "github_app_client_secret": "secret",
    "token_encryption_key": Fernet.generate_key().decode(),
}


def octo() -> SignedIn:
    return SignedIn(User(id=uuid4(), github_id=7, login="octo"), "ghu_1")


def client(settings: Settings, caller: Caller | None = None) -> TestClient:
    test_app = FastAPI()

    @test_app.post("/change")
    def change(_: Annotated[Caller, Depends(require_member)]) -> dict:
        return {}

    @test_app.post("/ask", dependencies=[Depends(limit_questions)])
    def ask() -> dict:
        return {}

    test_app.dependency_overrides[get_settings] = lambda: settings
    test_app.dependency_overrides[get_session] = lambda: None
    limiter = RateLimiter()
    test_app.dependency_overrides[get_question_limiter] = lambda: limiter
    if caller:
        test_app.dependency_overrides[get_caller] = lambda: caller
    return TestClient(test_app)


def test_without_sign_in_the_admin_key_rules_stay_the_same() -> None:
    assert client(Settings(_env_file=None)).post("/change").status_code == 200
    keyed = client(Settings(_env_file=None, admin_api_key="k"))
    assert keyed.post("/change").status_code == 401
    assert keyed.post("/change", headers={"X-Admin-Key": "k"}).status_code == 200


def test_with_sign_in_changes_need_a_user_or_the_admin_key() -> None:
    no_key = client(Settings(_env_file=None, **SIGN_IN))
    keyed = client(Settings(_env_file=None, admin_api_key="k", **SIGN_IN))
    signed_in = client(Settings(_env_file=None, **SIGN_IN), Caller(octo(), False))

    response = no_key.post("/change")
    assert response.status_code == 401
    assert response.json()["detail"] == "Sign in with GitHub to do this"
    assert keyed.post("/change", headers={"X-Admin-Key": "k"}).status_code == 200
    assert signed_in.post("/change").status_code == 200


def test_signed_in_users_get_their_own_higher_question_limit() -> None:
    settings = Settings(
        _env_file=None, questions_per_minute=1, signed_in_questions_per_minute=2
    )
    anonymous = client(settings, Caller(None, False))
    signed_in = client(settings, Caller(octo(), False))

    assert [anonymous.post("/ask").status_code for _ in range(2)] == [200, 429]
    assert [signed_in.post("/ask").status_code for _ in range(3)] == [200, 200, 429]
