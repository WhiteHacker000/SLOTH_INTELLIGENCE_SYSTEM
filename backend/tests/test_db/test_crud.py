from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import crud
from app.models import Comment, CommentKind, Discussion, DiscussionKind, Repository

CREATED = datetime(2026, 1, 2, tzinfo=UTC)


def make_repository(session: Session, full_name: str = "example/project") -> Repository:
    return crud.create_repository(
        session, full_name=full_name, html_url=f"https://github.com/{full_name}"
    )


def make_issue(session: Session, repository: Repository, title: str) -> Discussion:
    return crud.upsert_discussion(
        session,
        repository.id,
        kind=DiscussionKind.ISSUE,
        github_id=1001,
        number=7,
        title=title,
        body="Should we use pgvector?",
        state="open",
        labels=["design"],
        source_url="https://github.com/example/project/issues/7",
        created_at=CREATED,
    )


def test_create_and_read_repository(db_session: Session) -> None:
    repository = make_repository(db_session)

    assert crud.get_repository(db_session, repository.id) is repository
    assert crud.get_repository_by_full_name(db_session, "example/project") is repository
    assert crud.get_repository_by_full_name(db_session, "missing/repo") is None


def test_list_repositories_is_sorted_by_name(db_session: Session) -> None:
    make_repository(db_session, "zeta/project")
    make_repository(db_session, "alpha/project")

    names = [repo.full_name for repo in crud.list_repositories(db_session)]

    assert names == sorted(names)


def test_repository_full_name_is_unique(db_session: Session) -> None:
    make_repository(db_session)

    with pytest.raises(IntegrityError):
        make_repository(db_session)


def test_upsert_discussion_updates_instead_of_duplicating(db_session: Session) -> None:
    repository = make_repository(db_session)

    first = make_issue(db_session, repository, "Vector storage")
    second = make_issue(db_session, repository, "Vector storage (renamed)")

    count = db_session.scalar(select(func.count()).select_from(Discussion))
    assert count == 1
    assert second.id == first.id
    assert second.title == "Vector storage (renamed)"
    assert second.labels == ["design"]


def test_upsert_comment_updates_instead_of_duplicating(db_session: Session) -> None:
    issue = make_issue(db_session, make_repository(db_session), "Vector storage")

    for body in ("First draft", "Edited"):
        comment = crud.upsert_comment(
            db_session,
            issue.id,
            kind=CommentKind.ISSUE_COMMENT,
            github_id=5001,
            author="octocat",
            body=body,
            source_url="https://github.com/example/project/issues/7#issuecomment-5001",
            created_at=CREATED,
        )

    count = db_session.scalar(select(func.count()).select_from(Comment))
    assert count == 1
    assert comment.body == "Edited"


def test_failed_sync_keeps_previous_checkpoint(db_session: Session) -> None:
    repository = make_repository(db_session)

    crud.record_sync_result(db_session, repository)
    checkpoint = repository.last_synced_at
    crud.record_sync_result(db_session, repository, error="GitHub rate limit")

    assert checkpoint is not None
    assert repository.last_synced_at == checkpoint
    assert repository.last_sync_error == "GitHub rate limit"
