from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_session
from app.ingestion.github_client import (
    GitHubClient,
    GitHubError,
    RateLimitExceeded,
    RepositoryNotFound,
    create_github_client,
)
from app.models import Repository
from app.schemas.repositories import (
    RepositoryCreate,
    RepositoryDetail,
    RepositoryRead,
    RepositoryRegistered,
    SyncStarted,
    TokenRequest,
)
from app.services import repositories as service

router = APIRouter(prefix="/repositories", tags=["repositories"])

RATE_LIMIT_MESSAGE = "GitHub rate limit reached. Add your GitHub token to continue."

SessionDep = Annotated[Session, Depends(get_session)]
GitHubFactory = Callable[[str | None], GitHubClient]
SyncRunner = Callable[[UUID, str | None], None]


def get_github_factory() -> GitHubFactory:
    return create_github_client


def get_sync_runner() -> SyncRunner:
    return service.run_sync


@router.post(
    "", response_model=RepositoryRegistered, status_code=status.HTTP_201_CREATED
)
def register_repository(
    body: RepositoryCreate,
    session: SessionDep,
    github_factory: Annotated[GitHubFactory, Depends(get_github_factory)],
) -> RepositoryRegistered:
    try:
        with github_factory(body.token_value()) as github:
            repository, estimate = service.register_repository(
                session, github, body.full_name
            )
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
    background: BackgroundTasks,
    run_sync: Annotated[SyncRunner, Depends(get_sync_runner)],
    body: TokenRequest | None = None,
) -> SyncStarted:
    repository = _find(session, repository_id)
    token = body.token_value() if body else None
    background.add_task(run_sync, repository.id, token)
    return SyncStarted(repository_id=repository.id, message="Sync started")


def _find(session: Session, repository_id: UUID) -> Repository:
    repository = crud.get_repository(session, repository_id)
    if repository is None:
        raise HTTPException(404, "Repository not found")
    return repository
