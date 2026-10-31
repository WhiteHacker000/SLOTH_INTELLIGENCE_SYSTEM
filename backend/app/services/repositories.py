import logging
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import SessionLocal
from app.ingestion.estimate import estimate_import
from app.ingestion.github_client import GitHubReader, create_github_client
from app.ingestion.importer import import_repository
from app.models import Comment, Discussion, Repository, SyncStatus
from app.schemas.repositories import (
    ImportEstimateRead,
    RepositoryDetail,
    RepositoryRead,
)

logger = logging.getLogger(__name__)

UNEXPECTED_SYNC_ERROR = "Sync failed unexpectedly. Saved progress was kept."


def register_repository(
    session: Session, github: GitHubReader, full_name: str
) -> tuple[Repository, ImportEstimateRead]:
    """Check the repository exists on GitHub, save it, and estimate the import."""
    meta = github.get_json(f"/repos/{full_name}")
    estimate = ImportEstimateRead(**asdict(estimate_import(github, meta["full_name"])))

    repository = crud.get_repository_by_full_name(session, meta["full_name"])
    if repository is None:
        repository = crud.create_repository(
            session,
            full_name=meta["full_name"],
            github_id=meta["id"],
            html_url=meta["html_url"],
            description=meta.get("description"),
            default_branch=meta.get("default_branch"),
        )
    session.commit()
    return repository, estimate


def repository_detail(session: Session, repository: Repository) -> RepositoryDetail:
    discussion_ids = select(Discussion.id).where(
        Discussion.repository_id == repository.id
    )
    discussions = session.scalar(
        select(func.count()).select_from(discussion_ids.subquery())
    )
    comments = session.scalar(
        select(func.count())
        .select_from(Comment)
        .where(Comment.discussion_id.in_(discussion_ids))
    )
    base = RepositoryRead.model_validate(repository).model_dump()
    return RepositoryDetail(
        **base, discussion_count=discussions or 0, comment_count=comments or 0
    )


def run_sync(repository_id: UUID, token: str | None) -> None:
    """Run an import in the background with its own session.

    The token lives only in this call and is dropped when it returns.
    """
    with SessionLocal() as session, create_github_client(token) as github:
        repository = crud.get_repository(session, repository_id)
        if repository is None:
            return
        try:
            result = import_repository(session, github, repository, session.commit)
            session.commit()
        except Exception:
            logger.exception("Sync of %s crashed", repository.full_name)
            session.rollback()
            repository.sync_status = SyncStatus.FAILED
            repository.last_sync_error = UNEXPECTED_SYNC_ERROR
            session.commit()
            return
        logger.info("Sync of %s finished: %s", repository.full_name, result)
