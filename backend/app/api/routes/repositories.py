from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
    RepositoryRead,
    RepositoryRegistered,
)
from app.services import repositories as service

router = APIRouter(prefix="/repositories", tags=["repositories"])

RATE_LIMIT_MESSAGE = "GitHub rate limit reached. Add your GitHub token to continue."

SessionDep = Annotated[Session, Depends(get_session)]
GitHubFactory = Callable[[str | None], GitHubClient]


def get_github_factory() -> GitHubFactory:
    return create_github_client


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
