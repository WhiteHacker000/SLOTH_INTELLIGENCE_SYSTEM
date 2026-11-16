from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_session
from app.schemas.decisions import (
    PullRequestContext,
    PullRequestContextRequest,
    RelatedDecision,
)
from app.services.code_links import related_decisions
from app.services.decisions import list_decisions

router = APIRouter(tags=["pull requests"])


@router.post("/pr-context", response_model=PullRequestContext)
def pr_context(
    body: PullRequestContextRequest,
    session: Annotated[Session, Depends(get_session)],
) -> PullRequestContext:
    """Past decisions about the files a pull request changes."""
    repository = crud.get_repository_by_full_name(session, body.repository_full_name)
    if repository is None:
        raise HTTPException(404, "Repository not found")
    ranked = related_decisions(session, repository.id, body.files, body.limit)
    reads = {
        d.id: d
        for d in list_decisions(session, repository, [d_id for d_id, _, _ in ranked])
    }
    return PullRequestContext(
        repository_full_name=repository.full_name,
        decisions=[
            RelatedDecision(decision=reads[d_id], matched_files=files, score=score)
            for d_id, files, score in ranked
        ],
    )
