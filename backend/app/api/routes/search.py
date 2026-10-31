from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_session
from app.embeddings.embedder import Embedder, EmbeddingsUnavailable, get_embedder
from app.retrieval.search import search_chunks
from app.schemas.retrieval import RetrievalRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    body: RetrievalRequest,
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> SearchResponse:
    repository_id = None
    if body.repository_full_name:
        repository = crud.get_repository_by_full_name(
            session, body.repository_full_name
        )
        if repository is None:
            raise HTTPException(404, "Repository not found")
        repository_id = repository.id

    try:
        query_vector = embedder.embed_query(body.query)
    except EmbeddingsUnavailable as error:
        raise HTTPException(503, "Search is not set up on this server") from error

    results = search_chunks(
        session,
        query_vector,
        repository_id=repository_id,
        source_types=body.source_types,
        limit=body.limit,
    )
    return SearchResponse(query=body.query, results=results)
