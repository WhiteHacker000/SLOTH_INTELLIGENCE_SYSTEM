from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import crud
from app.ingestion.github_client import RateLimit, RateLimitExceeded, RepositoryNotFound
from app.ingestion.importer import RATE_LIMITED_ERROR, import_repository
from app.models import Comment, CommentKind, Discussion, DiscussionKind

API = "https://api.github.com/repos/a/b"
WEB = "https://github.com/a/b"
CREATED = "2026-01-02T00:00:00Z"


def item(number: int, pr: bool = False, **extra: Any) -> dict[str, Any]:
    data = {
        "id": 1000 + number,
        "number": number,
        "title": f"Item {number}",
        "body": "Discussion",
        "state": "open",
        "user": {"login": "octocat"},
        "labels": [],
        "html_url": f"{WEB}/issues/{number}",
        "created_at": CREATED,
    }
    if pr:
        data["pull_request"] = {"merged_at": None}
    return {**data, **extra}


def comment(github_id: int, parent_key: str, number: int) -> dict[str, Any]:
    return {
        "id": github_id,
        "body": "A comment",
        "user": {"login": "reviewer"},
        "html_url": f"{WEB}/issues/{number}#issuecomment-{github_id}",
        "created_at": CREATED,
        parent_key: f"{API}/issues/{number}",
    }


class FakeGitHub:
    authenticated = False

    def __init__(self, pages: dict[str, list[dict[str, Any]]], fail: str = "") -> None:
        self.pages = pages
        self.fail = fail
        self.rate_limit = RateLimit()
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self.fail == "missing":
            raise RepositoryNotFound("Repository or resource not found")
        return {
            "id": 1,
            "html_url": WEB,
            "description": "Demo",
            "default_branch": "main",
        }

    def paginate(self, path: str, params: dict[str, Any] | None = None):
        self.calls.append((path, params))
        if self.fail and self.fail in path:
            raise RateLimitExceeded(reset_at=None)
        return iter(self.pages.get(path, []))


def github_with_data(fail: str = "") -> FakeGitHub:
    return FakeGitHub(
        {
            "/repos/a/b/issues": [item(1), item(2, pr=True), {"id": "broken"}],
            "/repos/a/b/issues/comments": [
                comment(501, "issue_url", 1),
                comment(502, "issue_url", 99),
            ],
            "/repos/a/b/pulls/comments": [comment(601, "pull_request_url", 2)],
            "/repos/a/b/pulls/2/reviews": [
                {**comment(701, "x", 2), "created_at": None, "submitted_at": CREATED},
                {**comment(702, "x", 2), "body": ""},
            ],
        },
        fail,
    )


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_imports_discussions_comments_and_reviews(db_session: Session) -> None:
    repo = crud.create_repository(db_session, full_name="a/b", html_url=WEB)

    result = import_repository(db_session, github_with_data(), repo)

    assert (result.discussions, result.comments, result.paused) == (2, 3, False)
    kinds = db_session.scalars(select(Discussion.kind).order_by(Discussion.number))
    assert list(kinds) == [DiscussionKind.ISSUE, DiscussionKind.PULL_REQUEST]
    comment_kinds = set(db_session.scalars(select(Comment.kind)))
    assert comment_kinds == set(CommentKind)
    assert repo.github_id == 1
    assert repo.last_synced_at is not None
    assert repo.last_sync_error is None


def test_second_import_does_not_duplicate_and_uses_since(db_session: Session) -> None:
    repo = crud.create_repository(db_session, full_name="a/b", html_url=WEB)
    import_repository(db_session, github_with_data(), repo)
    checkpoint = repo.last_synced_at

    github = github_with_data()
    import_repository(db_session, github, repo)

    assert count(db_session, Discussion) == 2
    assert count(db_session, Comment) == 3
    issues_params = dict(github.calls)["/repos/a/b/issues"]
    assert checkpoint is not None and issues_params is not None
    assert issues_params["since"] == checkpoint.isoformat()


def test_rate_limit_pauses_and_keeps_checkpoint(db_session: Session) -> None:
    repo = crud.create_repository(db_session, full_name="a/b", html_url=WEB)

    result = import_repository(db_session, github_with_data(fail="/reviews"), repo)

    assert result.paused is True
    assert result.message == RATE_LIMITED_ERROR
    assert count(db_session, Discussion) == 2
    assert repo.last_synced_at is None
    assert repo.last_sync_error == RATE_LIMITED_ERROR


def test_missing_repository_is_recorded(db_session: Session) -> None:
    repo = crud.create_repository(db_session, full_name="a/b", html_url=WEB)

    result = import_repository(db_session, github_with_data(fail="missing"), repo)

    assert result.paused is False
    assert result.message == "Repository or resource not found"
    assert repo.last_sync_error == result.message
