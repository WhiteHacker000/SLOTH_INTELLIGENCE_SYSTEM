from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.lookups import embed_query, repository_id_for
from app.db.session import get_session
from app.embeddings.embedder import Embedder, get_embedder
from app.generation.answer import answer_from_evidence
from app.generation.llm import LanguageModel, LanguageModelError, get_language_model
from app.retrieval.search import search_chunks
from app.schemas.answers import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    session: Annotated[Session, Depends(get_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    model: Annotated[LanguageModel, Depends(get_language_model)],
) -> AskResponse:
    repository_id = repository_id_for(session, body.repository_full_name)
    evidence = search_chunks(
        session,
        embed_query(embedder, body.question),
        repository_id=repository_id,
        limit=body.limit,
    )
    try:
        return answer_from_evidence(model, body.question, evidence)
    except LanguageModelError as error:
        raise HTTPException(503, "The answer model is not available") from error
