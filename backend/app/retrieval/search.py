from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Comment,
    CommentKind,
    Discussion,
    DiscussionKind,
    DocumentChunk,
    Repository,
)
from app.schemas.github import DiscussionSourceType
from app.schemas.retrieval import RetrievedEvidence


def search_chunks(
    session: Session,
    query_vector: list[float],
    *,
    repository_id: UUID | None = None,
    source_types: list[DiscussionSourceType] | None = None,
    limit: int = 5,
) -> list[RetrievedEvidence]:
    """Return the chunks closest to the query, with where each one came from."""
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    query = (
        select(DocumentChunk, Discussion, Comment, Repository.full_name, distance)
        .join(Discussion, Discussion.id == DocumentChunk.discussion_id)
        .join(Repository, Repository.id == Discussion.repository_id)
        .outerjoin(Comment, Comment.id == DocumentChunk.comment_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    if repository_id is not None:
        query = query.where(Discussion.repository_id == repository_id)
    if source_types:
        # Body chunks take their type from the discussion, others from the comment.
        values = {source_type.value for source_type in source_types}
        discussion_kinds = [kind for kind in DiscussionKind if kind.value in values]
        comment_kinds = [kind for kind in CommentKind if kind.value in values]
        query = query.where(
            Comment.kind.in_(comment_kinds)
            | (
                DocumentChunk.comment_id.is_(None)
                & Discussion.kind.in_(discussion_kinds)
            )
        )

    results = []
    for chunk, discussion, comment, full_name, dist in session.execute(query):
        source = comment or discussion
        results.append(
            RetrievedEvidence(
                content=chunk.content,
                source_url=chunk.source_url,
                # Cosine similarity can dip below zero for unrelated text.
                similarity=max(0.0, min(1.0, 1 - dist)),
                repository_full_name=full_name,
                source_type=DiscussionSourceType(source.kind.value),
                discussion_number=discussion.number,
                discussion_title=discussion.title,
                author=source.author,
                created_at=source.created_at,
            )
        )
    return results
