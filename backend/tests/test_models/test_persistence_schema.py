from pgvector.sqlalchemy import Vector

from app.models.entities import (
    Decision,
    Discussion,
    DiscussionChunk,
    EvidenceReference,
    Repository,
)


def test_initial_postgres_entities_and_embedding_dimension_are_declared() -> None:
    assert {
        Repository.__tablename__,
        Discussion.__tablename__,
        Decision.__tablename__,
        EvidenceReference.__tablename__,
        DiscussionChunk.__tablename__,
    } == {
        "repositories",
        "discussions",
        "decisions",
        "evidence_references",
        "discussion_chunks",
    }
    assert isinstance(DiscussionChunk.__table__.c.embedding.type, Vector)
    assert DiscussionChunk.__table__.c.embedding.type.dim == 384
    assert Discussion.__table__.c.source_type.type.enums == [
        "issue",
        "pull_request",
        "issue_comment",
        "review_comment",
    ]
    assert Decision.__table__.c.status.type.enums == [
        "proposed",
        "accepted",
        "rejected",
        "unresolved",
    ]
