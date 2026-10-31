from pgvector.sqlalchemy import Vector

from app.db.base import Base
from app.models import Comment, Decision, Discussion, DocumentChunk


def test_all_phase_one_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "repositories",
        "discussions",
        "comments",
        "document_chunks",
        "decisions",
        "decision_evidence",
    }


def test_enum_columns_store_lowercase_values() -> None:
    assert Discussion.__table__.c.kind.type.enums == ["issue", "pull_request"]
    assert Comment.__table__.c.kind.type.enums == [
        "issue_comment",
        "review_comment",
        "review",
    ]
    assert Decision.__table__.c.status.type.enums == [
        "proposed",
        "accepted",
        "rejected",
        "unresolved",
    ]


def test_embedding_matches_bge_small_dimension() -> None:
    embedding_type = DocumentChunk.__table__.c.embedding.type

    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == 384


def test_github_sources_are_unique_for_idempotent_imports() -> None:
    def unique_columns(table) -> set[tuple[str, ...]]:
        return {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }

    assert ("repository_id", "number") in unique_columns(Discussion.__table__)
    assert ("kind", "github_id") in unique_columns(Comment.__table__)
