"""What signed-in users may do when sign-in is on and they are not the admin."""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.repositories import (
    get_extraction_runner,
    get_github_factory,
    get_sync_runner,
)
from app.auth import sessions
from app.auth.access import Caller, get_caller
from app.auth.push_access import get_push_access
from app.db import crud
from app.db.session import get_session
from app.main import app
from app.models import Repository
from tests.test_db.test_repository_api import FakeGitHub


class FakePushAccess:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def can_push(self, user: sessions.SignedIn, full_name: str) -> bool:
        return self.allowed


@pytest.fixture
def api(db_session: Session) -> Generator[dict[str, Any], None, None]:
    user = sessions.save_user(db_session, github_id=7, login="octo", avatar_url=None)
    state: dict[str, Any] = {"newest": 5, "tokens": [], "syncs": [], "runs": []}
    state["user"] = user

    def factory(token: str | None) -> FakeGitHub:
        state["tokens"].append(token)
        return FakeGitHub(token, state["newest"], False)

    caller = Caller(sessions.SignedIn(user, "ghu_user"), admin=False)
    app.dependency_overrides.update(
        {
            get_session: lambda: db_session,
            get_caller: lambda: caller,
            get_github_factory: lambda: factory,
            get_sync_runner: lambda: lambda *args: state["syncs"].append(args),
            get_extraction_runner: lambda: lambda *args: state["runs"].append(args),
            get_push_access: lambda: FakePushAccess(state.get("push", False)),
        }
    )
    state["client"] = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def repo(session: Session) -> Repository:
    return crud.create_repository(
        session, full_name="a/b", html_url="https://github.com/a/b"
    )


def test_only_people_who_can_push_run_extraction(
    api: dict, db_session: Session
) -> None:
    r = repo(db_session)

    refused = api["client"].post(f"/api/v1/repositories/{r.id}/extract")
    api["push"] = True
    allowed = api["client"].post(f"/api/v1/repositories/{r.id}/extract")

    assert refused.status_code == 403
    assert "push to a/b" in refused.json()["detail"]
    assert allowed.status_code == 202
