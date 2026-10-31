from dataclasses import asdict

from sqlalchemy.orm import Session

from app.db import crud
from app.ingestion.estimate import estimate_import
from app.ingestion.github_client import GitHubReader
from app.models import Repository
from app.schemas.repositories import ImportEstimateRead


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
