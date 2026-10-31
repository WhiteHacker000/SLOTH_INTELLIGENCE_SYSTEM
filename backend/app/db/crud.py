from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Comment, Discussion, Repository

ModelT = TypeVar("ModelT")


def get_repository(session: Session, repository_id: UUID) -> Repository | None:
    return session.get(Repository, repository_id)


def get_repository_by_full_name(session: Session, full_name: str) -> Repository | None:
    return session.scalars(
        select(Repository).where(Repository.full_name == full_name)
    ).one_or_none()


def list_repositories(session: Session) -> list[Repository]:
    return list(session.scalars(select(Repository).order_by(Repository.full_name)))


def create_repository(session: Session, **values: Any) -> Repository:
    repository = Repository(**values)
    session.add(repository)
    session.flush()
    return repository


def record_sync_result(
    session: Session,
    repository: Repository,
    error: str | None = None,
    started_at: datetime | None = None,
) -> None:
    """Advance the sync checkpoint only when the sync succeeded.

    Pass the time the sync started so items updated during the sync are
    picked up next time.
    """
    if error is None:
        repository.last_synced_at = started_at or datetime.now(UTC)
    repository.last_sync_error = error
    session.flush()


def upsert_discussion(
    session: Session, repository_id: UUID, **values: Any
) -> Discussion:
    statement = insert(Discussion).values(repository_id=repository_id, **values)
    statement = statement.on_conflict_do_update(
        constraint="uq_discussion_number",
        set_={column: statement.excluded[column] for column in values},
    )
    return _upsert(session, Discussion, statement)


def upsert_comment(session: Session, discussion_id: UUID, **values: Any) -> Comment:
    statement = insert(Comment).values(discussion_id=discussion_id, **values)
    statement = statement.on_conflict_do_update(
        constraint="uq_comment_source",
        set_={column: statement.excluded[column] for column in values},
    )
    return _upsert(session, Comment, statement)


def _upsert(session: Session, model: type[ModelT], statement: Any) -> ModelT:
    return session.scalars(
        statement.returning(model),
        execution_options={"populate_existing": True},
    ).one()
