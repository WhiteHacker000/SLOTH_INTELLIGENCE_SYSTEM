import logging
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import SessionLocal
from app.embeddings.embedder import EmbeddingsUnavailable, get_embedder
from app.embeddings.pipeline import embed_pending_chunks
from app.ingestion.estimate import estimate_import
from app.ingestion.github_client import GitHubReader, create_github_client
from app.ingestion.importer import import_repository
from app.models import Comment, Decision, Discussion, Repository, SyncStatus
from app.processing.chunks import chunk_repository
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
    decisions = session.scalar(
        select(func.count()).where(Decision.repository_id == repository.id)
    )
    base = RepositoryRead.model_validate(repository).model_dump()
    return RepositoryDetail(
        **base,
        discussion_count=discussions or 0,
        comment_count=comments or 0,
        decision_count=decisions or 0,
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
        build_search_index(session, repository)


def build_search_index(session: Session, repository: Repository) -> None:
    """Chunk and embed imported text.

    Search is optional for now, so a failure here is logged and does not undo
    the import.
    """
    try:
        stats = chunk_repository(session, repository.id)
        session.commit()
        embedded = embed_pending_chunks(
            session, get_embedder(), repository.id, session.commit
        )
        session.commit()
    except EmbeddingsUnavailable as error:
        logger.warning("Skipping embeddings for %s: %s", repository.full_name, error)
        return
    except Exception:
        logger.exception("Search index for %s failed", repository.full_name)
        session.rollback()
        return
    logger.info("Indexed %s: %s, %d embedded", repository.full_name, stats, embedded)
