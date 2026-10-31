from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.lookups import embed_query, repository_id_for
from app.db.session import get_session
from app.embeddings.embedder import Embedder, get_embedder
from app.retrieval.search import search_chunks
from app.schemas.retrieval import RetrievalRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    body: RetrievalRequest,
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> SearchResponse:
    repository_id = repository_id_for(session, body.repository_full_name)
    results = search_chunks(
        session,
        embed_query(embedder, body.query),
        repository_id=repository_id,
        source_types=body.source_types,
        limit=body.limit,
    )
    return SearchResponse(query=body.query, results=results)
