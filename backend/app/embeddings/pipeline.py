from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.embedder import Embedder
from app.models import Discussion, DocumentChunk

BATCH_SIZE = 64


def embed_pending_chunks(
    session: Session,
    embedder: Embedder,
    repository_id: UUID,
    save_progress: Callable[[], None] = lambda: None,
) -> int:
    """Embed chunks that have no embedding yet, one batch at a time.

    Returns how many chunks were embedded.
    """
    query = (
        select(DocumentChunk)
        .join(Discussion, Discussion.id == DocumentChunk.discussion_id)
        .where(
            Discussion.repository_id == repository_id,
            DocumentChunk.embedding.is_(None),
        )
        .order_by(DocumentChunk.id)
        .limit(BATCH_SIZE)
    )
    embedded = 0
    while chunks := session.scalars(query).all():
        vectors = embedder.embed_documents([chunk.content for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        session.flush()
        save_progress()
        embedded += len(chunks)
    return embedded
