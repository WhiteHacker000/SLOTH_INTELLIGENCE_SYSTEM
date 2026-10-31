from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Comment, Discussion, DiscussionKind, DocumentChunk
from app.processing.text import clean_markdown, split_into_chunks

ChunkKey = tuple[UUID, UUID | None, int]


@dataclass
class ChunkStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0


def chunk_repository(session: Session, repository_id: UUID) -> ChunkStats:
    """Create or refresh searchable chunks for every discussion and comment.

    Unchanged chunks keep their embedding. Changed chunks lose it so it gets
    recomputed. Chunks whose text no longer exists are deleted.
    """
    discussions = session.scalars(
        select(Discussion).where(Discussion.repository_id == repository_id)
    ).all()
    discussion_ids = [discussion.id for discussion in discussions]
    comments: dict[UUID, list[Comment]] = defaultdict(list)
    for comment in session.scalars(
        select(Comment).where(Comment.discussion_id.in_(discussion_ids))
    ):
        comments[comment.discussion_id].append(comment)
    existing: dict[ChunkKey, DocumentChunk] = {
        (chunk.discussion_id, chunk.comment_id, chunk.ordinal): chunk
        for chunk in session.scalars(
            select(DocumentChunk).where(DocumentChunk.discussion_id.in_(discussion_ids))
        )
    }

    stats = ChunkStats()
    for discussion in discussions:
        heading = _heading(discussion)
        sources = [(None, discussion.source_url, discussion.body)]
        sources += [(c.id, c.source_url, c.body) for c in comments[discussion.id]]
        for comment_id, source_url, body in sources:
            pieces = split_into_chunks(clean_markdown(body)) if body else []
            if not pieces and comment_id is None:
                pieces = [""]  # the title alone is still worth searching
            for ordinal, piece in enumerate(pieces):
                content = f"{heading}\n\n{piece}".rstrip()
                key = (discussion.id, comment_id, ordinal)
                chunk = existing.pop(key, None)
                if chunk is None:
                    session.add(
                        DocumentChunk(
                            discussion_id=discussion.id,
                            comment_id=comment_id,
                            ordinal=ordinal,
                            content=content,
                            source_url=source_url,
                        )
                    )
                    stats.created += 1
                elif chunk.content != content:
                    chunk.content, chunk.embedding = content, None
                    stats.updated += 1
                else:
                    stats.unchanged += 1

    for chunk in existing.values():
        session.delete(chunk)
        stats.deleted += 1
    session.flush()
    return stats


def _heading(discussion: Discussion) -> str:
    # Gives comment chunks the context of the issue or PR they belong to.
    kind = "Pull request" if discussion.kind is DiscussionKind.PULL_REQUEST else "Issue"
    return f"{kind} #{discussion.number}: {discussion.title}"
