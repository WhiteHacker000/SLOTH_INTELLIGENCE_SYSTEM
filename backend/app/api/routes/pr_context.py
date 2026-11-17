import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_session
from app.embeddings.embedder import Embedder, EmbeddingsUnavailable, get_embedder
from app.embeddings.pipeline import embed_pending_decisions
from app.models import Repository
from app.schemas.decisions import (
    PullRequestContext,
    PullRequestContextRequest,
    RelatedDecision,
)
from app.services.code_links import related_decisions
from app.services.decisions import list_decisions

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pull requests"])

# Enough of a PR description to say what it is about.
MAX_DESCRIPTION_CHARS = 2000


@router.post("/pr-context", response_model=PullRequestContext)
def pr_context(
    body: PullRequestContextRequest,
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> PullRequestContext:
    """Past decisions about the files a pull request changes, or its topic."""
    repository = crud.get_repository_by_full_name(session, body.repository_full_name)
    if repository is None:
        raise HTTPException(404, "Repository not found")
    text = f"{body.title}\n{body.body[:MAX_DESCRIPTION_CHARS]}".strip()
    vector = _embed(session, embedder, repository, text) if text else None
    ranked = related_decisions(session, repository.id, body.files, body.limit, vector)
    reads = {
        d.id: d
        for d in list_decisions(session, repository, [m.decision_id for m, _ in ranked])
    }
    return PullRequestContext(
        repository_full_name=repository.full_name,
        decisions=[
            RelatedDecision(
                decision=reads[m.decision_id],
                matched_files=m.files,
                similarity=m.similarity,
                score=score,
            )
            for m, score in ranked
        ],
    )


def _embed(
    session: Session, embedder: Embedder, repository: Repository, text: str
) -> list[float] | None:
    """Embed the PR text, first embedding any decisions that have no vector yet.

    Without the embedding model installed, matching falls back to files only.
    """
    try:
        if embed_pending_decisions(session, embedder, repository.id):
            session.commit()
        return embedder.embed_query(text)
    except EmbeddingsUnavailable:
        logger.info("Embeddings not installed; matching pull requests by file only")
        return None
