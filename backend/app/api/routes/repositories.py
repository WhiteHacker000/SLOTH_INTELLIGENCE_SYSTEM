from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.access import Caller, MemberDep
from app.auth.push_access import PushAccess, get_push_access
from app.db import crud
from app.db.session import get_session
from app.ingestion.github_client import (
    GitHubClient,
    GitHubError,
    RateLimitExceeded,
    RepositoryNotFound,
    create_github_client,
)
from app.models import JobKind, Repository, SyncStatus
from app.schemas.decisions import DecisionRead, ExtractionStarted
from app.schemas.repositories import (
    RepositoryCreate,
    RepositoryDetail,
    RepositoryRead,
    RepositoryRegistered,
    SyncStarted,
    TokenRequest,
)
from app.services import (
    decisions as decision_service,
    jobs,
    repositories as service,
    worker,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])

RATE_LIMIT_MESSAGE = "GitHub rate limit reached. Add your GitHub token to continue."
# Bigger repositories need a maintainer to install SilS on them.
MAX_IMPORT_THREADS = 5_000
SYNCS_PER_DAY = 20

SessionDep = Annotated[Session, Depends(get_session)]
GitHubFactory = Callable[[str | None], GitHubClient]
SyncRunner = Callable[[UUID, str | None, UUID | None], None]
ExtractionRunner = Callable[[UUID, list[UUID]], None]


def get_github_factory() -> GitHubFactory:
    return create_github_client


def get_sync_runner() -> SyncRunner:
    return worker.queue_sync


def get_extraction_runner() -> ExtractionRunner:
    return worker.queue_extraction


@router.post(
    "", response_model=RepositoryRegistered, status_code=status.HTTP_201_CREATED
)
def register_repository(
    body: RepositoryCreate,
    session: SessionDep,
    caller: MemberDep,
    github_factory: Annotated[GitHubFactory, Depends(get_github_factory)],
) -> RepositoryRegistered:
    max_items = None if caller.admin else MAX_IMPORT_THREADS
    try:
        with github_factory(body.token_value() or _user_token(caller)) as github:
            repository, estimate = service.register_repository(
                session, github, body.full_name, max_items
            )
    except service.RepositoryTooLarge as error:
        raise HTTPException(
            403,
            f"This repository has over {MAX_IMPORT_THREADS:,} issues and pull "
            "requests. A maintainer can install SilS on it to import it.",
        ) from error
    except RepositoryNotFound as error:
        raise HTTPException(404, "Repository not found on GitHub") from error
    except RateLimitExceeded as error:
        raise HTTPException(429, RATE_LIMIT_MESSAGE) from error
    except GitHubError as error:
        raise HTTPException(502, "Could not reach GitHub, try again") from error
    return RepositoryRegistered(
        repository=RepositoryRead.model_validate(repository), estimate=estimate
    )


@router.get("", response_model=list[RepositoryRead])
def list_repositories(session: SessionDep) -> list[Repository]:
    return crud.list_repositories(session)


@router.get("/{repository_id}", response_model=RepositoryDetail)
def get_repository(repository_id: UUID, session: SessionDep) -> RepositoryDetail:
    return service.repository_detail(session, _find(session, repository_id))


@router.post(
    "/{repository_id}/sync",
    response_model=SyncStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_repository(
    repository_id: UUID,
    session: SessionDep,
    caller: MemberDep,
    run_sync: Annotated[SyncRunner, Depends(get_sync_runner)],
    body: TokenRequest | None = None,
) -> SyncStarted:
    repository = _find(session, repository_id)
    user_id = caller.user.user.id if caller.user else None
    if user_id and not caller.admin:
        _check_sync_limits(session, user_id)
    token = (body.token_value() if body else None) or _user_token(caller)
    # Show "running" straight away instead of after the background task starts.
    repository.sync_status = SyncStatus.RUNNING
    session.commit()
    run_sync(repository.id, token, user_id)
    return SyncStarted(repository_id=repository.id, message="Sync started")


@router.get("/{repository_id}/decisions", response_model=list[DecisionRead])
def list_decisions(repository_id: UUID, session: SessionDep) -> list[DecisionRead]:
    return decision_service.list_decisions(session, _find(session, repository_id))


@router.post(
    "/{repository_id}/extract",
    response_model=ExtractionStarted,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_repository_decisions(
    repository_id: UUID,
    session: SessionDep,
    caller: MemberDep,
    push_access: Annotated[PushAccess, Depends(get_push_access)],
    run_extraction: Annotated[ExtractionRunner, Depends(get_extraction_runner)],
) -> ExtractionStarted:
    repository = _find(session, repository_id)
    # Extraction runs Gemma for minutes, so only the repository's maintainers
    # can start it.
    if not caller.admin and not (
        caller.user and push_access.can_push(caller.user, repository.full_name)
    ):
        raise HTTPException(
            403, f"Only people who can push to {repository.full_name} can run this"
        )
    if jobs.has_active(session, repository.id, JobKind.EXTRACT):
        return ExtractionStarted(
            repository_id=repository.id,
            threads=0,
            message="Extraction is already running",
        )
    threads = decision_service.threads_to_extract(session, repository.id)
    if threads:
        run_extraction(repository.id, threads)
    message = "Extraction started" if threads else "All threads are already processed"
    return ExtractionStarted(
        repository_id=repository.id, threads=len(threads), message=message
    )


def _user_token(caller: Caller) -> str | None:
    return caller.user.github_token if caller.user else None


def _check_sync_limits(session: Session, user_id: UUID) -> None:
    started = jobs.syncs_started_by(
        session, user_id, datetime.now(UTC) - timedelta(days=1)
    )
    if any(job.status in jobs.ACTIVE for job in started):
        raise HTTPException(
            429, "Your last import is still running. Try again after it finishes."
        )
    if len(started) >= SYNCS_PER_DAY:
        raise HTTPException(
            429, f"You can start {SYNCS_PER_DAY} imports a day. Try again tomorrow."
        )


def _find(session: Session, repository_id: UUID) -> Repository:
    repository = crud.get_repository(session, repository_id)
    if repository is None:
        raise HTTPException(404, "Repository not found")
    return repository
