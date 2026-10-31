from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.schemas.decisions import DecisionStatus

EMBEDDING_DIMENSION = 384


class DiscussionKind(StrEnum):
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"


class CommentKind(StrEnum):
    ISSUE_COMMENT = "issue_comment"
    REVIEW_COMMENT = "review_comment"
    REVIEW = "review"


def _enum_column(enum_cls: type[StrEnum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    html_url: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )


class Discussion(Base):
    """An issue or pull request. Its comments live in `comments`."""

    __tablename__ = "discussions"
    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_discussion_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[DiscussionKind] = mapped_column(
        _enum_column(DiscussionKind, "discussion_kind")
    )
    github_id: Mapped[int] = mapped_column(BigInteger)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(32))
    author: Mapped[str | None] = mapped_column(String(255))
    labels: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Comment(Base):
    __tablename__ = "comments"
    # GitHub uses a separate id sequence for each comment kind.
    __table_args__ = (UniqueConstraint("kind", "github_id", name="uq_comment_source"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    discussion_id: Mapped[UUID] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[CommentKind] = mapped_column(_enum_column(CommentKind, "comment_kind"))
    github_id: Mapped[int] = mapped_column(BigInteger)
    author: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        # comment_id is NULL for chunks of the issue/PR body itself.
        UniqueConstraint(
            "discussion_id",
            "comment_id",
            "ordinal",
            name="uq_chunk_position",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    discussion_id: Mapped[UUID] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[list[str]] = mapped_column(JSONB, default=list)
    alternatives: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    trade_offs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[DecisionStatus] = mapped_column(
        _enum_column(DecisionStatus, "decision_status"), index=True
    )
    # Model self-reported score, not a calibrated probability.
    confidence: Mapped[float | None] = mapped_column(Float)
    extraction_model: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now
    )


class DecisionEvidence(Base):
    __tablename__ = "decision_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    discussion_id: Mapped[UUID] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    excerpt: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048))
