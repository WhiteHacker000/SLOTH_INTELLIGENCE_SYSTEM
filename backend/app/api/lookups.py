from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.embeddings.embedder import Embedder, EmbeddingsUnavailable


def repository_id_for(session: Session, full_name: str | None) -> UUID | None:
    """Turn an optional owner/name filter into an id, or 404 if unknown."""
    if not full_name:
        return None
    repository = crud.get_repository_by_full_name(session, full_name)
    if repository is None:
        raise HTTPException(404, "Repository not found")
    return repository.id


def embed_query(embedder: Embedder, text: str) -> list[float]:
    try:
        return embedder.embed_query(text)
    except EmbeddingsUnavailable as error:
        raise HTTPException(503, "Search is not set up on this server") from error
